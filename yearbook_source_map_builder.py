import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

SEEDS_PATH = Path('yearbook_arc_seeds.json')
INDEX_DIR = Path('archive/index')
POSTS_DIR = Path('archive/posts')
TWEETS_DIR = Path('archive/tweets')
OUTPUT_JSON = Path('yearbook/source_map.json')
OUTPUT_MD = Path('yearbook/source_map.md')
ARCHIVE_STATE = Path('archive_state.json')


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
        json.dump(value, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write('\n')


def load_jsonl(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in paths:
        if not path.exists() or path.name.startswith('all_'):
            continue
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    row['_archive_file'] = str(path)
                    rows.append(row)
                except json.JSONDecodeError:
                    continue
    return rows


def text_blob(row: Dict[str, Any]) -> str:
    return ' '.join(str(row.get(k) or '') for k in ('title', 'slug', 'excerpt', 'text', 'html')).lower()


def item_ref(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': row.get('id'),
        'source': row.get('source'),
        'title': row.get('title'),
        'url': row.get('url'),
        'published_at': row.get('published_at') or row.get('created_at'),
        'tags': row.get('tags') or [],
        'archive_file': row.get('_archive_file'),
    }


def build_source_map(seeds: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    arcs_out = []
    for arc in seeds.get('arcs', []):
        keywords = [k.lower() for k in arc.get('keywords', [])]
        players = [p.lower() for p in arc.get('players', [])]
        tags = [t.lower() for t in arc.get('tags', [])]

        matches = []
        for row in rows:
            blob = text_blob(row)
            row_tags = [str(t).lower() for t in (row.get('tags') or [])]
            if any(k in blob for k in keywords) or any(p in blob for p in players) or any(t in row_tags for t in tags):
                matches.append(item_ref(row))

        matches.sort(key=lambda x: x.get('published_at') or '')
        arcs_out.append(
            {
                'name': arc.get('name'),
                'range': arc.get('range'),
                'keywords': arc.get('keywords', []),
                'players': arc.get('players', []),
                'tags': arc.get('tags', []),
                'sources': matches,
                'source_count': len(matches),
            }
        )

    return {
        'generated_at': utcnow_iso(),
        'arc_count': len(arcs_out),
        'arcs': arcs_out,
    }


def to_markdown(source_map: Dict[str, Any]) -> str:
    lines = ['# Yearbook Source Map', '', f"Generated: {source_map.get('generated_at')}", '']
    for arc in source_map.get('arcs', []):
        lines.append(f"## {arc.get('name')} ({arc.get('range')})")
        lines.append(f"Sources: {arc.get('source_count', 0)}")
        for src in arc.get('sources', []):
            title = src.get('title') or src.get('id') or '(untitled)'
            stamp = src.get('published_at') or 'unknown-date'
            lines.append(f"- {stamp} | {title} | {src.get('archive_file')}")
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description='Build yearbook source map from archive files and index data.')
    parser.add_argument('--seeds', default=str(SEEDS_PATH))
    parser.add_argument('--index-dir', default=str(INDEX_DIR))
    parser.add_argument('--posts-dir', default=str(POSTS_DIR))
    parser.add_argument('--tweets-dir', default=str(TWEETS_DIR))
    parser.add_argument('--output-json', default=str(OUTPUT_JSON))
    parser.add_argument('--output-md', default=str(OUTPUT_MD))
    parser.add_argument('--state-file', default=str(ARCHIVE_STATE))
    args = parser.parse_args()

    seeds = read_json(Path(args.seeds), {'arcs': []})

    _ = read_json(Path(args.index_dir) / 'summary.json', {})

    rows = load_jsonl(sorted(Path(args.posts_dir).glob('**/*.jsonl')) + sorted(Path(args.tweets_dir).glob('**/*.jsonl')))
    source_map = build_source_map(seeds, rows)

    write_json(Path(args.output_json), source_map)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(to_markdown(source_map), encoding='utf-8')

    state = read_json(Path(args.state_file), {'version': 1, 'counts': {}})
    state['last_yearbook_source_map_utc'] = utcnow_iso()
    write_json(Path(args.state_file), state)

    print(f"Yearbook source map written: {args.output_json}, {args.output_md}")


if __name__ == '__main__':
    main()
