import os
from typing import Optional

from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_pregame_html
from dtlib.nba_sources import get_game_by_id
from dtlib.state_io import load_all, save_all
from dtlib.utils import is_abs_http_url, parse_iso, slugify, utcnow, utcnow_iso

WINDOWS = {6, 5, 4, 3, 2, 1}


def _is_demo_mode() -> bool:
    return str(os.getenv('DT_FORCE_DEMO', '')).strip().lower() == 'true'


def _hero_image(game: dict, season_config: dict, series_config: dict) -> Optional[str]:
    game_id = game.get('game_id')
    url = game.get('library', {}).get('feature_image_src') or game.get('assets', {}).get('game_image')
    if not url:
        pattern = (
            season_config.get('asset_patterns', {}).get('game_image')
            or series_config.get('asset_patterns', {}).get('game_image')
            or 'https://storage.ghost.io/c/f2/f9/f2f98597-fc28-4a31-8135-86802fa12f06/content/images/2026/04/{game_id}.png'
        )
        if game_id:
            url = pattern.format(game_id=game_id)
    return url if is_abs_http_url(url) else None


def eligible_game(games, *, target_game_id: Optional[str] = None, force_demo: bool = False) -> Optional[dict]:
    if force_demo and target_game_id:
        return get_game_by_id(games, target_game_id)

    now = utcnow()
    candidates = []
    for game in games:
        tip = parse_iso(game.get('tipoff_utc'))
        if not tip or game.get('status') == 'final':
            continue
        hours = int(round((tip - now).total_seconds() / 3600.0))
        if hours in WINDOWS:
            candidates.append((tip, game))
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1] if candidates else None


def main() -> None:
    data = load_all()
    force_demo = _is_demo_mode()
    target_game_id = os.getenv('DT_TARGET_GAME_ID', '').strip() or None

    game = eligible_game(data['season_state'].get('games', []), target_game_id=target_game_id, force_demo=force_demo)
    if not game:
        print('No eligible pregame window.')
        return

    opponent = game.get('opponent') or 'Opponent'
    if game.get('season_phase') == 'playoffs' and game.get('game_number_in_series'):
        title = f"Game {game.get('game_number_in_series')} Pregame Primer: Thunder vs. {opponent}"
        round_label = data['series_config'].get('round_label') or data['season_config'].get('round_label') or game.get('series_round') or 'Playoffs'
        custom_excerpt = f"{round_label}, Game {game.get('game_number_in_series')}"
    else:
        title = f'Pregame Primer: Thunder vs. {opponent}'
        location = game.get('library', {}).get('location')
        custom_excerpt = f"{game.get('local_date') or 'TBD'}" + (f" • {location}" if location else '')

    slug = game['automation'].get('pregame_slug') or slugify(f"pregame {game.get('game_id') or game.get('local_date')} {opponent}")
    html = build_pregame_html(game, data['season_config'])
    ghost = GhostClient()
    existing = ghost.find_post_by_slug(slug) if ghost.enabled else None
    if existing and existing.get('status') == 'published':
        print(f'Pregame already published, skipping: {slug}')
        return

    post = ghost.upsert_draft(
        title=title,
        slug=slug,
        html=html,
        tags=['Thunder', 'Pregame'],
        feature_image=_hero_image(game, data['season_config'], data['series_config']),
        custom_excerpt=custom_excerpt,
        update_if_unpublished=True,
    )

    if not ghost.is_real_post(post):
        print('Pregame dry-run only; not mutating state.')
        return

    game['automation']['pregame_slug'] = slug
    data['content_state'].setdefault('ghost_posts', {})[slug] = {'id': post.get('id'), 'lane': 'pregame', 'updated_utc': utcnow_iso()}
    save_all(data)
    print(f'Pregame upserted: {slug}')


if __name__ == '__main__':
    main()
