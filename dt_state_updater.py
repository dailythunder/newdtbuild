from dtlib.nba_sources import compute_live_window, game_links, refresh_todays_status
from dtlib.state_io import load_all, save_all
from dtlib.utils import utcnow_iso


def main() -> None:
    data = load_all()
    season_state = data['season_state']
    content_state = data['content_state']
    team_state = data['team_state']
    stats_state = data['stats_state']

    for game in season_state.get('games', []):
        game['links'] = game_links(game.get('game_id'))

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
