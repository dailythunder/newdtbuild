from datetime import timedelta
from typing import Any, Dict, List, Optional

import requests

from .utils import parse_iso, utcnow, utcnow_iso

NBA_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json,text/html,application/xhtml+xml',
    'Referer': 'https://www.nba.com/',
}


def game_links(game_id: Optional[str]) -> Dict[str, Optional[str]]:
    gid = str(game_id).strip() if game_id else ''
    if not gid:
        return {'nba_game': None, 'nba_box': None, 'nba_pbp': None, 'courtsketch': None}
    return {
        'nba_game': f'https://www.nba.com/game/{gid}',
        'nba_box': f'https://www.nba.com/game/{gid}/box-score',
        'nba_pbp': f'https://www.nba.com/game/{gid}/play-by-play',
        'courtsketch': f'https://courtsketch.com/live_game/{gid.lstrip("0")}',
    }


def refresh_todays_status(games: List[Dict[str, Any]]) -> None:
    try:
        r = requests.get(
            'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json',
            headers=NBA_HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        todays = r.json().get('scoreboard', {}).get('games', [])
    except Exception:
        return

    by_id = {str(g.get('gameId')): g for g in todays}
    for game in games:
        gid = str(game.get('game_id') or '')
        live = by_id.get(gid)
        if not live:
            continue
        status = str(live.get('gameStatus', ''))
        if status == '3':
            game['status'] = 'final'
        elif status == '2':
            game['status'] = 'live'
        else:
            game['status'] = 'scheduled'

        home_score = int(live.get('homeTeam', {}).get('score') or 0)
        away_score = int(live.get('awayTeam', {}).get('score') or 0)
        if game.get('home_away') == 'home':
            game['thunder_score'], game['opponent_score'] = home_score, away_score
        else:
            game['thunder_score'], game['opponent_score'] = away_score, home_score

        if game['status'] == 'final' and game['thunder_score'] is not None and game['opponent_score'] is not None:
            game['result'] = 'W' if game['thunder_score'] > game['opponent_score'] else 'L'
        game['timestamps']['last_verified_utc'] = utcnow_iso()


def compute_live_window(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    now = utcnow()
    dated: List[Dict[str, Any]] = []
    for g in games:
        tip = parse_iso(g.get('tipoff_utc'))
        if tip:
            dated.append({'tipoff': tip, 'game': g})
    dated.sort(key=lambda x: x['tipoff'])

    completed = [
        item['game']
        for item in dated
        if item['game'].get('status') == 'final' or (item['tipoff'] < now and item['game'].get('result'))
    ]
    upcoming = [item['game'] for item in dated if item['tipoff'] >= now - timedelta(hours=2)]

    previous = completed[-1] if completed else None
    next_games = upcoming[:7]
    return {
        'generated_at_utc': utcnow_iso(),
        'previous_game': previous,
        'next_games': next_games,
    }
