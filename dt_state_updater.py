from dtlib.nba_sources import compute_live_window, game_links, refresh_todays_status
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
