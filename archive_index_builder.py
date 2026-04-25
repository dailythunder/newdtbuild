import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

ARCHIVE_STATE = Path('archive_state.json')
POSTS_DIR = Path('archive/posts')
TWEETS_DIR = Path('archive/tweets')
INDEX_DIR = Path('archive/index')
GAME_ID_RE = re.compile(r'\b0\d{9}\b')
PLAYER_TERMS = [
    'Shai', 'Gilgeous-Alexander', 'Jalen Williams', 'JDub', 'Chet', 'Holmgren',
    'Dort', 'Caruso', 'Hartenstein', 'Isaiah Joe', 'Cason Wallace', 'Ajay Mitchell',
    'Wiggins', 'Jaylin Williams', 'JWill', 'Topic', 'Dieng', 'Kenrich', 'Krich',
]
TOPIC_TERMS = [
    'playoffs', 'MVP', 'defense', 'free throws', 'injury', 'hamstring', 'trade',
    'draft', 'Presti', 'Loud City', 'scoreboard', 'day after', 'podcast', 'bolts',
]


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


def iter_jsonl(paths: Iterable[Path]) -> Iterable[Dict[str, Any]]:
    for path in paths:
        if not path.exists():
            continue
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row['_archive_file'] = str(path)
                yield row


def item_key(row: Dict[str, Any]) -> str:
    return str(row.get('id') or row.get('slug') or row.get('created_at') or row.get('title') or row.get('text') or '')


def text_blob(row: Dict[str, Any]) -> str:
    return ' '.join(str(row.get(k) or '') for k in ('title', 'slug', 'excerpt', 'text', 'html'))


def short_ref(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': row.get('id'),
        'source': row.get('source'),
        'title': row.get('title'),
        'slug': row.get('slug'),
        'url': row.get('url'),
        'created_at': row.get('created_at'),
        'published_at': row.get('published_at'),
        'tags': row.get('tags'),
        'archive_file': row.get('_archive_file'),
    }


def add(index: Dict[str, List[Dict[str, Any]]], key: str, row: Dict[str, Any]) -> None:
    if not key:
        return
    index[key].append(short_ref(row))


def build_indexes(posts_dir: Path, tweets_dir: Path) -> Dict[str, Any]:
    rows = list(iter_jsonl(list(posts_dir.glob('**/*.jsonl')) + list(tweets_dir.glob('**/*.jsonl'))))
    by_game: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_year: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_tag: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_player: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_topic: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_post_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in rows:
        blob = text_blob(row)
        for gid in sorted(set((row.get('game_ids') or []) + GAME_ID_RE.findall(blob))):
            add(by_game, gid, row)

        dt = row.get('published_at') or row.get('created_at')
        if isinstance(dt, str) and len(dt) >= 4:
            add(by_year, dt[:4], row)

        for tag in row.get('tags') or []:
            add(by_tag, str(tag).lower(), row)
            tag_l = str(tag).lower()
            if 'pregame' in tag_l:
                add(by_post_type, 'pregame', row)
            elif 'scoreboard' in tag_l:
                add(by_post_type, 'scoreboard', row)
            elif 'day after' in tag_l:
                add(by_post_type, 'day_after', row)
            elif 'podcast' in tag_l:
                add(by_post_type, 'podcast', row)

        blob_l = blob.lower()
        for term in PLAYER_TERMS:
            if term.lower() in blob_l:
                add(by_player, term.lower(), row)
        for term in TOPIC_TERMS:
            if term.lower() in blob_l:
                add(by_topic, term.lower(), row)

    return {
        'counts': {
            'items': len(rows),
            'games': len(by_game),
            'years': len(by_year),
            'tags': len(by_tag),
            'players': len(by_player),
            'topics': len(by_topic),
        },
        'by_game': by_game,
        'by_year': by_year,
        'by_tag': by_tag,
        'by_player': by_player,
        'by_topic': by_topic,
        'by_post_type': by_post_type,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Build lightweight indexes from archived Ghost posts and tweets.')
    parser.add_argument('--posts-dir', default=str(POSTS_DIR))
    parser.add_argument('--tweets-dir', default=str(TWEETS_DIR))
    parser.add_argument('--output-dir', default=str(INDEX_DIR))
    parser.add_argument('--state-file', default=str(ARCHIVE_STATE))
    args = parser.parse_args()

    indexes = build_indexes(Path(args.posts_dir), Path(args.tweets_dir))
    out = Path(args.output_dir)
    write_json(out / 'by_game.json', indexes['by_game'])
    write_json(out / 'by_year.json', indexes['by_year'])
    write_json(out / 'by_tag.json', indexes['by_tag'])
    write_json(out / 'by_player.json', indexes['by_player'])
    write_json(out / 'by_topic.json', indexes['by_topic'])
    write_json(out / 'by_post_type.json', indexes['by_post_type'])
    write_json(out / 'summary.json', indexes['counts'])

    state_path = Path(args.state_file)
    state = read_json(state_path, {'version': 1, 'counts': {}})
    state['last_index_build_utc'] = utcnow_iso()
    state['index_counts'] = indexes['counts']
    write_json(state_path, state)
    print(f'Archive index build complete: {indexes["counts"]}')


if __name__ == '__main__':
    main()
