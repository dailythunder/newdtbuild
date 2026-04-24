import os

from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_dayafter_html
from dtlib.nba_sources import (
    compute_live_window,
    get_game_by_id,
    playoff_series_status_after_game,
    regular_record_after_game,
)
from dtlib.state_io import load_all, save_all
from dtlib.utils import is_abs_http_url, slugify, utcnow_iso


def _is_demo_mode() -> bool:
    return str(os.getenv('DT_FORCE_DEMO', '')).strip().lower() == 'true'


def _hero_image(game: dict, season_config: dict, series_config: dict):
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


def _scoreboard_image(game: dict, season_config: dict, series_config: dict) -> str:
    if game.get('result') == 'W':
        pattern = season_config.get('asset_patterns', {}).get('scoreboard_win_image') or series_config.get('asset_patterns', {}).get('scoreboard_win_image')
        return pattern.format(index=1) if pattern else ''
    pattern = season_config.get('asset_patterns', {}).get('scoreboard_loss_image') or series_config.get('asset_patterns', {}).get('scoreboard_loss_image')
    return pattern.format(index=1) if pattern else ''


def _subtitle(games, game):
    if game.get('season_phase') == 'playoffs':
        return playoff_series_status_after_game(games, game)
    return regular_record_after_game(games, game)


def main() -> None:
    data = load_all()
    games = data['season_state'].get('games', [])
    force_demo = _is_demo_mode()
    target_game_id = os.getenv('DT_TARGET_GAME_ID', '').strip() or None

    if force_demo and target_game_id:
        previous = get_game_by_id(games, target_game_id)
    else:
        previous = compute_live_window(games)['previous_game']

    if not previous or previous.get('status') != 'final':
        print('No final game for day after.')
        return

    ghost = GhostClient()
    ghost_posts = data['content_state'].setdefault('ghost_posts', {})
    opponent = previous.get('opponent') or 'Opponent'
    title = f"Thunder {previous.get('thunder_score')}, {opponent} {previous.get('opponent_score')}: The Day After Report"
    slug = previous['automation'].get('dayafter_slug') or slugify(f"day after {previous.get('game_id')} {opponent}")

    existing = ghost.find_post_by_slug(slug) if ghost.enabled else None
    if existing and existing.get('status') == 'published':
        print('Day after already published.')
        return

    if previous.get('result') == 'W':
        caption = f"Thunder def. {opponent}, {previous.get('thunder_score')}-{previous.get('opponent_score')}"
    else:
        caption = f"{opponent} def. Thunder, {previous.get('opponent_score')}-{previous.get('thunder_score')}"

    scoreboard_image = _scoreboard_image(previous, data['season_config'], data['series_config'])
    post = ghost.upsert_draft(
        title=title,
        slug=slug,
        html=build_dayafter_html(previous, scoreboard_image, caption),
        tags=['day after report', f"thunder {opponent.lower()}"],
        feature_image=_hero_image(previous, data['season_config'], data['series_config']),
        custom_excerpt=_subtitle(games, previous),
        update_if_unpublished=force_demo,
    )

    if not ghost.is_real_post(post):
        print('Day after dry-run only; not mutating completion state.')
        print(f'TITLE={title}')
        print(f'EXCERPT={_subtitle(games, previous)}')
        print(f"TAGS={['day after report', f'thunder {opponent.lower()}']}")
        return

    previous['automation']['dayafter_slug'] = slug
    previous['automation']['dayafter_complete'] = True
    ghost_posts[slug] = {'id': post.get('id'), 'lane': 'dayafter', 'updated_utc': utcnow_iso()}
    save_all(data)
    print(f'Day after created: {slug}')


if __name__ == '__main__':
    main()
