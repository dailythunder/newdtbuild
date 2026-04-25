import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ARCHIVE_STATE = Path('archive_state.json')
DEFAULT_SOURCE = Path('archive_sources/tweets.js')
DEFAULT_OUTPUT_DIR = Path('archive/tweets')
URL_RE = re.compile(r'https?://\S+')


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


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
            count += 1
    return count


def parse_twitter_js(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding='utf-8', errors='replace').strip()
    if '=' in raw[:200]:
        raw = raw.split('=', 1)[1].strip()
    raw = raw.rstrip(';')
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError('Expected tweets.js to contain a list')
    return data


def parse_created_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ('%a %b %d %H:%M:%S %z %Y', '%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def extract_entities(tweet: Dict[str, Any]) -> Dict[str, List[str]]:
    entities = tweet.get('entities') or {}
    urls = []
    for entry in entities.get('urls') or []:
        expanded = entry.get('expanded_url') or entry.get('url')
        if expanded:
            urls.append(expanded)

    hashtags = [h.get('text') for h in entities.get('hashtags') or [] if h.get('text')]
    mentions = [m.get('screen_name') for m in entities.get('user_mentions') or [] if m.get('screen_name')]
    media = []
    for m in (entities.get('media') or []) + ((tweet.get('extended_entities') or {}).get('media') or []):
        media_url = m.get('media_url_https') or m.get('media_url') or m.get('expanded_url')
        if media_url and media_url not in media:
            media.append(media_url)

    return {'urls': urls, 'hashtags': hashtags, 'mentions': mentions, 'media': media}


def normalize_archive_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tweet = item.get('tweet') if isinstance(item.get('tweet'), dict) else item
    if not isinstance(tweet, dict):
        return None

    created = parse_created_at(tweet.get('created_at'))
    text = tweet.get('full_text') or tweet.get('text') or ''
    entities = extract_entities(tweet)

    for url in URL_RE.findall(text):
        if url not in entities['urls']:
            entities['urls'].append(url)

    return {
        'id': str(tweet.get('id_str') or tweet.get('id') or ''),
        'created_at': created.isoformat().replace('+00:00', 'Z') if created else tweet.get('created_at'),
        'year': created.year if created else None,
        'text': text,
        'urls': entities['urls'],
        'hashtags': entities['hashtags'],
        'mentions': entities['mentions'],
        'media': entities['media'],
        'favorite_count': int(tweet.get('favorite_count') or 0),
        'retweet_count': int(tweet.get('retweet_count') or 0),
        'reply_to_status_id': tweet.get('in_reply_to_status_id_str'),
        'reply_to_screen_name': tweet.get('in_reply_to_screen_name'),
        'source': 'twitter_archive',
    }


def bucket_path(row: Dict[str, Any], output_dir: Path) -> Path:
    year = row.get('year') or 'unknown'
    return output_dir / f'{year}.jsonl'


def main() -> None:
    parser = argparse.ArgumentParser(description='Ingest Twitter archive tweets.js into JSONL files.')
    parser.add_argument('--source', default=str(DEFAULT_SOURCE))
    parser.add_argument('--output-dir', default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument('--state-file', default=str(ARCHIVE_STATE))
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        raise SystemExit('Missing archive_sources/tweets.js')

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        for old in output_dir.glob('**/*.jsonl'):
            old.unlink()

    rows = [r for r in (normalize_archive_item(item) for item in parse_twitter_js(source)) if r]

    by_path: Dict[Path, List[Dict[str, Any]]] = {}
    for row in rows:
        by_path.setdefault(bucket_path(row, output_dir), []).append(row)

    total = 0
    for path, chunk in sorted(by_path.items()):
        count = write_jsonl(path, chunk)
        total += count
        print(f'Wrote {count} tweets -> {path}')

    write_jsonl(output_dir / 'all_tweets.jsonl', rows)
    print(f'Wrote {len(rows)} tweets -> {output_dir / "all_tweets.jsonl"}')

    state = read_json(Path(args.state_file), {'version': 1, 'counts': {}})
    state['last_twitter_ingest_utc'] = utcnow_iso()
    state.setdefault('counts', {})['tweets'] = total
    write_json(Path(args.state_file), state)
    print(f'Twitter ingest complete: {total} tweets')


if __name__ == '__main__':
    main()
