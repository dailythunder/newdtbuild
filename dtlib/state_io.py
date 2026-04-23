import json
from pathlib import Path
from typing import Any, Dict

from .utils import utcnow_iso

ROOT = Path(__file__).resolve().parent.parent
SEASON_CONFIG_PATH = ROOT / 'season_config.json'
SEASON_STATE_PATH = ROOT / 'season_state.json'
SERIES_CONFIG_PATH = ROOT / 'series_config.json'
CONTENT_STATE_PATH = ROOT / 'content_state.json'
TEAM_STATE_PATH = ROOT / 'team_state.json'
STATS_STATE_PATH = ROOT / 'stats_state.json'


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, value: Any) -> None:
    with path.open('w', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def default_content_state() -> Dict[str, Any]:
    return {
        'version': 2,
        'ghost_posts': {},
        'podcast_seen_keys': [],
        'bolts_seen_urls': [],
        'lanes': {
            'pregame': {},
            'scoreboard': {},
            'dayafter': {},
            'podcast': {},
            'bolts': {'active': False},
        },
        'runs': [],
        'last_successful_run_utc': None,
        'last_run_summary': {},
    }


def default_team_state() -> Dict[str, Any]:
    return {
        'team': 'OKC',
        'season_label': '2025-26',
        'roster': [],
        'availability': {'injury_status': []},
        'likely_starters': [],
        'active_group': [],
        'last_verified_utc': None,
    }


def default_stats_state() -> Dict[str, Any]:
    return {
        'team': 'OKC',
        'season_label': '2025-26',
        'team_season': {},
        'player_season': {},
        'rolling_last_5': {},
        'rolling_last_10': {},
        'milestones': {},
        'last_refreshed_utc': None,
    }


def default_game() -> Dict[str, Any]:
    return {
        'season_phase': 'regular',
        'series_round': None,
        'game_number_in_series': None,
        'game_id': None,
        'opponent': None,
        'opponent_full_name': None,
        'home_away': None,
        'local_date': None,
        'tipoff_utc': None,
        'status': 'scheduled',
        'result': None,
        'thunder_score': None,
        'opponent_score': None,
        'links': {},
        'library': {
            'tv': None,
            'line': None,
            'location': None,
            'feature_image_src': None,
            'feature_image_srcset': None,
            'matchup_matrix_src': None,
            'matchup_matrix_srcset': None,
            'okc_injuries': [],
            'opp_injuries': [],
            'okc_likely_starters': [],
            'opp_likely_starters': [],
        },
        'assets': {'game_image': None, 'scoreboard_image': None},
        'automation': {
            'pregame_slug': None,
            'scoreboard_slug': None,
            'dayafter_slug': None,
            'podcast_slug': None,
            'pregame_complete': False,
            'scoreboard_complete': False,
            'dayafter_complete': False,
        },
        'timestamps': {'last_verified_utc': None},
    }


def default_season_state() -> Dict[str, Any]:
    return {
        'team': 'OKC',
        'season_label': '2025-26',
        'generated_at_utc': utcnow_iso(),
        'playoff_placeholders': {'R2': None, 'WCF': None, 'Finals': None},
        'games': [],
    }


def normalize_game(game: Dict[str, Any]) -> Dict[str, Any]:
    merged = default_game()
    merged.update(game or {})
    if not isinstance(merged.get('library'), dict):
        merged['library'] = default_game()['library']
    if not isinstance(merged.get('assets'), dict):
        merged['assets'] = default_game()['assets']
    if not isinstance(merged.get('automation'), dict):
        merged['automation'] = default_game()['automation']
    if not isinstance(merged.get('timestamps'), dict):
        merged['timestamps'] = {'last_verified_utc': None}
    return merged


def load_all() -> Dict[str, Any]:
    season_config = read_json(SEASON_CONFIG_PATH, {})
    series_config = read_json(SERIES_CONFIG_PATH, {})
    season_state = read_json(SEASON_STATE_PATH, default_season_state())
    content_state = read_json(CONTENT_STATE_PATH, default_content_state())
    team_state = read_json(TEAM_STATE_PATH, default_team_state())
    stats_state = read_json(STATS_STATE_PATH, default_stats_state())

    season_state.setdefault('games', [])
    season_state['games'] = [normalize_game(g) for g in season_state.get('games', []) if isinstance(g, dict)]
    content_state.setdefault('ghost_posts', {})
    content_state.setdefault('podcast_seen_keys', [])
    content_state.setdefault('lanes', default_content_state()['lanes'])

    return {
        'season_config': season_config,
        'series_config': series_config,
        'season_state': season_state,
        'content_state': content_state,
        'team_state': team_state,
        'stats_state': stats_state,
    }


def save_all(data: Dict[str, Any]) -> None:
    write_json(SEASON_STATE_PATH, data['season_state'])
    write_json(CONTENT_STATE_PATH, data['content_state'])
    write_json(TEAM_STATE_PATH, data['team_state'])
    write_json(STATS_STATE_PATH, data['stats_state'])
