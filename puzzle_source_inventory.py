import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path('.')
OUTPUT_CSV = Path('puzzle/source_inventory.csv')
OUTPUT_JSON = Path('puzzle/source_inventory.json')
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


def classify_path(path: Path) -> str:
    normalized = str(path).replace('\\', '/')
    if normalized.startswith('archive_sources/'):
        return 'archive_source'
    if normalized.startswith('archive/posts/'):
        return 'archive_post_data'
    if normalized.startswith('archive/tweets/'):
        return 'archive_tweet_data'
    if normalized.startswith('archive/index/'):
        return 'archive_index'
    if normalized.startswith('yearbook/'):
        return 'yearbook'
    if normalized.startswith('puzzle/'):
        return 'puzzle'
    if normalized.startswith('.github/workflows/'):
        return 'workflow'
    if path.suffix == '.py':
        return 'python_script'
    if path.suffix in {'.json', '.jsonl'}:
        return 'json_data'
    if path.suffix in {'.md'}:
        return 'docs'
    return 'other'


def collect_inventory(repo_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted(repo_root.rglob('*')):
        if path.is_dir() or '.git' in path.parts or '__pycache__' in path.parts:
            continue
        rel = path.relative_to(repo_root)
        stat = path.stat()
        rows.append(
            {
                'path': str(rel).replace('\\', '/'),
                'category': classify_path(rel),
                'size_bytes': stat.st_size,
                'modified_utc': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace('+00:00', 'Z'),
            }
        )
    return rows


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['path', 'category', 'size_bytes', 'modified_utc'])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description='Build puzzle source inventory from archive sources and repository files.')
    parser.add_argument('--repo-root', default=str(REPO_ROOT))
    parser.add_argument('--output-csv', default=str(OUTPUT_CSV))
    parser.add_argument('--output-json', default=str(OUTPUT_JSON))
    parser.add_argument('--state-file', default=str(ARCHIVE_STATE))
    args = parser.parse_args()

    rows = collect_inventory(Path(args.repo_root))
    write_csv(Path(args.output_csv), rows)
    write_json(Path(args.output_json), {'generated_at': utcnow_iso(), 'count': len(rows), 'items': rows})

    state = read_json(Path(args.state_file), {'version': 1, 'counts': {}})
    state['last_puzzle_source_inventory_utc'] = utcnow_iso()
    write_json(Path(args.state_file), state)

    print(f'Puzzle source inventory written: {args.output_csv}, {args.output_json}')


if __name__ == '__main__':
    main()
