from dtlib.nba_sources import compute_live_window, game_links, refresh_todays_status
from dtlib.injury_sources import refresh_game_injuries
from dtlib.state_io import load_all, save_all
from dtlib.utils import is_abs_http_url, utcnow_iso


HERO_FALLBACK = 'https://storage.ghost.io/c/f2/f9/f2f98597-fc28-4a31-8135-86802fa12f06/content/images/2026/04/{game_id}.png'


def _merge_links(game: dict) -> None:
    existing = game.get('links') if isinstance(game.get('links'), dict) else {}
    fresh = game_links(game.get('game_id'))
    merged = dict(existing)
    for k, v in fresh.items():
        if v:
            merged[k] = v
        else:
            merged.setdefault(k, None)
    game['links'] = merged


def _preserve_library_and_assets(game: dict, season_config: dict, series_config: dict) -> None:
    library = game.setdefault('library', {})
    assets = game.setdefault('assets', {})
    game_id = game.get('game_id')

    if not library.get('feature_image_src') and is_abs_http_url(assets.get('game_image')):
        library['feature_image_src'] = assets['game_image']

    if not is_abs_http_url(assets.get('game_image')) and is_abs_http_url(library.get('feature_image_src')):
        assets['game_image'] = library['feature_image_src']

    if not library.get('feature_image_src') and game_id:
        pattern = (
            season_config.get('asset_patterns', {}).get('game_image')
            or series_config.get('asset_patterns', {}).get('game_image')
            or HERO_FALLBACK
        )
        library['feature_image_src'] = pattern.format(game_id=game_id)
        assets['game_image'] = library['feature_image_src']

    if not library.get('matchup_matrix_src'):
        matrix = season_config.get('asset_patterns', {}).get('matchup_matrix_image') or series_config.get('asset_patterns', {}).get('matchup_matrix_image')
        if matrix:
            library['matchup_matrix_src'] = matrix.format(game_id=game_id) if '{game_id}' in matrix else matrix

    for key in ('okc_injuries', 'opp_injuries', 'okc_likely_starters', 'opp_likely_starters'):
        value = library.get(key)
        if not isinstance(value, list):
            library[key] = []


def _injury_refresh_scope(games: list[dict], window: dict) -> list[dict]:
    scoped: dict[str, dict] = {}
    previous = window.get('previous_game')
    if previous and previous.get('game_id'):
        scoped[str(previous['game_id'])] = previous
    for game in window.get('next_games', []):
        if game.get('game_id'):
            scoped[str(game['game_id'])] = game

    active_series_keys = set()
    for game in games:
        if game.get('season_phase') != 'playoffs':
            continue
        if game.get('status') in {'final', 'completed'}:
            continue
        active_series_keys.add((game.get('opponent'), game.get('series_round')))
    for game in games:
        if game.get('season_phase') != 'playoffs':
            continue
        key = (game.get('opponent'), game.get('series_round'))
        if key in active_series_keys and game.get('game_id'):
            scoped[str(game['game_id'])] = game

    return list(scoped.values())


def main() -> None:
    data = load_all()
    season_state = data['season_state']
    content_state = data['content_state']
    team_state = data['team_state']
    stats_state = data['stats_state']

    for game in season_state.get('games', []):
        _merge_links(game)
        _preserve_library_and_assets(game, data['season_config'], data['series_config'])

    refresh_todays_status(season_state.get('games', []))
    window = compute_live_window(season_state.get('games', []))
    for game in _injury_refresh_scope(season_state.get('games', []), window):
        refresh_game_injuries(game)

    content_state['last_successful_run_utc'] = utcnow_iso()
    content_state['last_run_summary'] = {
        'lane': 'state_updater',
        'previous_game_id': window['previous_game'].get('game_id') if window['previous_game'] else None,
        'next_game_ids': [g.get('game_id') for g in window['next_games']],
        'game_count': len(season_state.get('games', [])),
    }
    season_state['generated_at_utc'] = utcnow_iso()
    team_state['last_verified_utc'] = utcnow_iso()
    stats_state['last_refreshed_utc'] = utcnow_iso()

    save_all(data)
    print('State updater complete.')


if __name__ == '__main__':
    main()
