import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode

import jwt
import requests

ARCHIVE_STATE = Path('archive_state.json')
DEFAULT_OUTPUT_DIR = Path('archive/posts')
GAME_ID_RE = re.compile(r'\b0\d{9}\b')
TAG_RE = re.compile(r'<[^>]+>')
SCRIPT_RE = re.compile(r'<script\b[^>]*>.*?</script>', re.I | re.S)
STYLE_RE = re.compile(r'<style\b[^>]*>.*?</style>', re.I | re.S)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write('\n')


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open('a', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
            count += 1
    return count


def clean_text(html: str) -> str:
    text = SCRIPT_RE.sub(' ', html or '')
    text = STYLE_RE.sub(' ', text)
    text = re.sub(r'</(p|div|h\d|li|blockquote)>', '\n', text, flags=re.I)
    text = TAG_RE.sub(' ', text)
    text = unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()


def parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def ghost_token(admin_key: str) -> str:
    key_id, secret = admin_key.split(':')
    iat = int(time.time())
    payload = {'iat': iat, 'exp': iat + 5 * 60, 'aud': '/admin/'}
    return jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})


def fetch_posts(base_url: str, admin_key: str, include_drafts: bool = False) -> List[Dict[str, Any]]:
    base = base_url.rstrip('/')
    headers = {'Authorization': f'Ghost {ghost_token(admin_key)}'}
    status_filter = '' if include_drafts else 'status:published'
    page = 1
    posts: List[Dict[str, Any]] = []

    while True:
        params = {
            'limit': 100,
            'page': page,
            'include': 'tags,authors',
            'formats': 'html',
            'order': 'published_at asc',
        }
        if status_filter:
            params['filter'] = status_filter
        url = f'{base}/ghost/api/admin/posts/?{urlencode(params)}'
        r = requests.get(url, headers=headers, timeout=60)
        print(f'Ghost posts page {page}: {r.status_code}')
        r.raise_for_status()
        payload = r.json()
        batch = payload.get('posts', []) or []
        posts.extend(batch)
        pagination = (payload.get('meta') or {}).get('pagination') or {}
        pages = int(pagination.get('pages') or page)
        if page >= pages or not batch:
            break
        page += 1

    return posts


def normalize_post(post: Dict[str, Any]) -> Dict[str, Any]:
    html = post.get('html') or ''
    text = clean_text(html)
    published_at = post.get('published_at') or post.get('updated_at') or post.get('created_at')
    tags = [t.get('name') for t in post.get('tags', []) if isinstance(t, dict) and t.get('name')]
    authors = [a.get('name') for a in post.get('authors', []) if isinstance(a, dict) and a.get('name')]
    game_ids = sorted(set(GAME_ID_RE.findall(' '.join([post.get('title') or '', post.get('slug') or '', html, text]))))
    return {
        'id': post.get('id'),
        'uuid': post.get('uuid'),
        'title': post.get('title'),
        'slug': post.get('slug'),
        'url': post.get('url'),
        'status': post.get('status'),
        'visibility': post.get('visibility'),
        'featured': bool(post.get('featured')),
        'published_at': published_at,
        'updated_at': post.get('updated_at'),
        'primary_tag': (post.get('primary_tag') or {}).get('name') if isinstance(post.get('primary_tag'), dict) else None,
        'tags': tags,
        'authors': authors,
        'excerpt': post.get('excerpt') or post.get('custom_excerpt'),
        'feature_image': post.get('feature_image'),
        'game_ids': game_ids,
        'html': html,
        'text': text,
        'source': 'ghost_admin_api',
    }


def bucket_path(row: Dict[str, Any], output_dir: Path) -> Path:
    dt = parse_date(row.get('published_at')) or parse_date(row.get('updated_at')) or datetime.now(timezone.utc)
    return output_dir / f'{dt.year}' / f'{dt.month:02d}.jsonl'


def main() -> None:
    parser = argparse.ArgumentParser(description='Ingest Ghost posts into chunked JSONL archive files.')
    parser.add_argument('--output-dir', default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument('--include-drafts', action='store_true')
    parser.add_argument('--state-file', default=str(ARCHIVE_STATE))
    args = parser.parse_args()

    ghost_url = os.getenv('GHOST_URL', '').strip()
    admin_key = os.getenv('GHOST_ADMIN_KEY', '').strip()
    if not ghost_url or not admin_key:
        raise SystemExit('Missing GHOST_URL or GHOST_ADMIN_KEY')

    output_dir = Path(args.output_dir)
    posts = fetch_posts(ghost_url, admin_key, include_drafts=args.include_drafts)
    rows = [normalize_post(p) for p in posts]

    # Rebuild Ghost post archive atomically by clearing only generated JSONL files under output_dir.
    if output_dir.exists():
        for old in output_dir.glob('**/*.jsonl'):
            old.unlink()

    by_path: Dict[Path, List[Dict[str, Any]]] = {}
    for row in rows:
        by_path.setdefault(bucket_path(row, output_dir), []).append(row)

    written = 0
    for path, chunk in sorted(by_path.items()):
        written += append_jsonl(path, chunk)
        print(f'Wrote {len(chunk)} rows -> {path}')

    all_path = output_dir / 'all_posts.jsonl'
    append_jsonl(all_path, rows)
    print(f'Wrote {len(rows)} rows -> {all_path}')

    state_path = Path(args.state_file)
    state = read_json(state_path, {'version': 1, 'counts': {}})
    state['last_ghost_ingest_utc'] = utcnow_iso()
    state.setdefault('counts', {})['ghost_posts'] = written
    write_json(state_path, state)
    print(f'Ghost ingest complete: {written} posts')


if __name__ == '__main__':
    main()
