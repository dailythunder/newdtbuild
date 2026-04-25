# Daily Thunder Private Archive Repo

This repository is for **private archive ingestion, indexing, yearbook source maps, and puzzle-source preparation**.

## Scope
- Ghost archive ingestion into JSONL files.
- Twitter archive ingestion from `archive_sources/tweets.js`.
- Archive index generation from ingested post/tweet data.
- Yearbook source map generation from seeded arcs.
- Puzzle source inventory generation from archive sources and repo files.

## Not In Scope
- Ghost post creation.
- Publishing anything.
- Production post automation.

## Setup
1. Install dependencies:
   - `pip install -r requirements.txt`
2. For Ghost ingest, configure environment/secrets:
   - `GHOST_URL`
   - `GHOST_ADMIN_KEY`

## Commands
- Ghost ingest:
  - `python archive_ingest_ghost.py`
- Twitter ingest:
  - `python archive_ingest_tweets.py`
- Archive index:
  - `python archive_index_builder.py`
- Yearbook source map:
  - `python yearbook_source_map_builder.py`
- Puzzle source inventory:
  - `python puzzle_source_inventory.py`

## Generated outputs
- `archive/posts/YYYY/MM.jsonl`
- `archive/posts/all_posts.jsonl`
- `archive/tweets/YYYY.jsonl`
- `archive/tweets/all_tweets.jsonl`
- `archive/index/by_game.json`
- `archive/index/by_year.json`
- `archive/index/by_tag.json`
- `archive/index/by_player.json`
- `archive/index/by_topic.json`
- `archive/index/by_post_type.json`
- `archive/index/summary.json`
- `yearbook/source_map.json`
- `yearbook/source_map.md`
- `puzzle/source_inventory.csv`
- `puzzle/source_inventory.json`
