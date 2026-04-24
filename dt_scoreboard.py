import os

from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_scoreboard_html
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


def _scoreboard_image_and_next(game: dict, content_state: dict, season_config: dict, series_config: dict):
    lanes = content_state.setdefault('lanes', {})
    rotation = lanes.setdefault('scoreboard', {}).setdefault('rotation', {'next_win_index': 1, 'next_loss_index': 1})

    result = game.get('result')
    win_size = int(season_config.get('scoreboard_rotation', {}).get('wins', 15))
    loss_size = int(season_config.get('scoreboard_rotation', {}).get('losses', 4))
    win_pattern = (
        season_config.get('asset_patterns', {}).get('scoreboard_win_image')
        or series_config.get('asset_patterns', {}).get('scoreboard_win_image')
        or 'https://storage.ghost.io/c/f2/f9/f2f98597-fc28-4a31-8135-86802fa12f06/content/images/2026/04/THUNDER-WIN-{index}.png'
    )
    loss_pattern = (
        season_config.get('asset_patterns', {}).get('scoreboard_loss_image')
        or series_config.get('asset_patterns', {}).get('scoreboard_loss_image')
        or 'https://storage.ghost.io/c/f2/f9/f2f98597-fc28-4a31-8135-86802fa12f06/content/images/2026/04/THUNDER-LOSE-{index}.png'
    )

    if result == 'W':
        idx = int(rotation.get('next_win_index', 1))
        image = win_pattern.format(index=idx)
        return (image if is_abs_http_url(image) else ''), ('next_win_index', 1 if idx >= win_size else idx + 1)

    idx = int(rotation.get('next_loss_index', 1))
    image = loss_pattern.format(index=idx)
    return (image if is_abs_http_url(image) else ''), ('next_loss_index', 1 if idx >= loss_size else idx + 1)


def _line_for_game(games, game):
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
        print('No final game for scoreboard.')
        return

    ghost = GhostClient()
    ghost_posts = data['content_state'].setdefault('ghost_posts', {})
    slug = previous['automation'].get('scoreboard_slug') or slugify(f"scoreboard {previous.get('game_id')}")

    existing = ghost.find_post_by_slug(slug) if ghost.enabled else None
    if existing and existing.get('status') == 'published':
        print('Scoreboard already published.')
        return

    opponent = previous.get('opponent') or 'Opponent'
    title = f"Scoreboard: Thunder vs. {opponent}"

    if previous.get('season_phase') == 'playoffs':
        round_label = data['series_config'].get('round_label') or data['season_config'].get('round_label') or previous.get('series_round') or 'Playoffs'
        custom_excerpt = f"Results from {round_label}, Game {previous.get('game_number_in_series') or '?'}"
    else:
        custom_excerpt = f"Results from {previous.get('local_date') or 'TBD'}"

    feature_image, next_rotation = _scoreboard_image_and_next(previous, data['content_state'], data['season_config'], data['series_config'])
    post = ghost.upsert_draft(
        title=title,
        slug=slug,
        html=build_scoreboard_html(previous, _line_for_game(games, previous)),
        tags=['thunder scoreboard', f"thunder {opponent.lower()}"],
        feature_image=feature_image,
        custom_excerpt=custom_excerpt,
        update_if_unpublished=force_demo,
    )

    if not ghost.is_real_post(post):
        print('Scoreboard dry-run only; not mutating completion state.')
        print(f'TITLE={title}')
        if previous.get('result') == 'W':
            print(f'HEADER=Final: Thunder def. {opponent}, {previous.get("thunder_score")}-{previous.get("opponent_score")}')
        else:
            print(f'HEADER=Final: {opponent} def. Thunder, {previous.get("opponent_score")}-{previous.get("thunder_score")}')
        print(f"TAGS={['thunder scoreboard', f'thunder {opponent.lower()}']}")
        print(f'FEATURE_IMAGE={feature_image}')
        return

    previous['automation']['scoreboard_slug'] = slug
    previous['automation']['scoreboard_complete'] = True
    data['content_state'].setdefault('lanes', {}).setdefault('scoreboard', {}).setdefault('rotation', {'next_win_index': 1, 'next_loss_index': 1})[next_rotation[0]] = next_rotation[1]
    ghost_posts[slug] = {'id': post.get('id'), 'lane': 'scoreboard', 'updated_utc': utcnow_iso()}
    save_all(data)
    print(f'Scoreboard created: {slug}')


if __name__ == '__main__':
    main()
