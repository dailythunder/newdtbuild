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


def get_game_by_id(games: List[Dict[str, Any]], game_id: Optional[str]) -> Optional[Dict[str, Any]]:
    wanted = str(game_id or '').strip()
    if not wanted:
        return None
    for game in games:
        if str(game.get('game_id') or '').strip() == wanted:
            return game
    return None


def latest_completed_game(games: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    completed: List[tuple] = []
    now = utcnow()
    for game in games:
        tip = parse_iso(game.get('tipoff_utc'))
        if not tip:
            continue
        is_complete = game.get('status') == 'final' or game.get('status') == 'completed' or (tip < now and bool(game.get('result')))
        if is_complete:
            completed.append((tip, game))
    completed.sort(key=lambda x: x[0])
    return completed[-1][1] if completed else None


def next_upcoming_games(games: List[Dict[str, Any]], limit: int = 7) -> List[Dict[str, Any]]:
    now = utcnow()
    upcoming: List[tuple] = []
    for game in games:
        tip = parse_iso(game.get('tipoff_utc'))
        if not tip:
            continue
        if game.get('status') in {'final', 'completed'}:
            continue
        if tip >= now - timedelta(hours=2):
            upcoming.append((tip, game))
    upcoming.sort(key=lambda x: x[0])
    return [game for _, game in upcoming[:limit]]


def refresh_todays_status(games: List[Dict[str, Any]]) -> None:
    try:
        r = requests.get(
            'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json',
            headers=NBA_HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        todays = r.json().get('scoreboard', {}).get('games', [])
    except Exception as exc:
        print(f'NBA scoreboard refresh skipped: {exc}')
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
        game.setdefault('timestamps', {})['last_verified_utc'] = utcnow_iso()


def compute_live_window(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    dated: List[tuple] = []
    for game in games:
        tip = parse_iso(game.get('tipoff_utc'))
        if tip:
            dated.append((tip, game))
    dated.sort(key=lambda x: x[0])

    previous = latest_completed_game([game for _, game in dated])
    next_games = next_upcoming_games([game for _, game in dated], limit=7)
    return {'previous_game': previous, 'next_games': next_games}


def regular_record_after_game(games: List[Dict[str, Any]], game: Dict[str, Any]) -> str:
    target_id = str(game.get('game_id') or '')
    wins = 0
    losses = 0
    dated = sorted(((parse_iso(g.get('tipoff_utc')), g) for g in games if parse_iso(g.get('tipoff_utc'))), key=lambda x: x[0])
    for _, g in dated:
        if g.get('season_phase') == 'playoffs':
            continue
        if g.get('status') == 'final' and g.get('result') in {'W', 'L'}:
            if g.get('result') == 'W':
                wins += 1
            else:
                losses += 1
        if str(g.get('game_id') or '') == target_id:
            break
    return f'OKC {wins}-{losses} on the season'


def playoff_series_status_after_game(games: List[Dict[str, Any]], game: Dict[str, Any]) -> str:
    target_id = str(game.get('game_id') or '')
    opponent = game.get('opponent')
    round_id = game.get('series_round')
    okc_wins = 0
    opp_wins = 0
    dated = sorted(((parse_iso(g.get('tipoff_utc')), g) for g in games if parse_iso(g.get('tipoff_utc'))), key=lambda x: x[0])
    for _, g in dated:
        if g.get('season_phase') != 'playoffs':
            continue
        if g.get('opponent') != opponent or g.get('series_round') != round_id:
            continue
        if g.get('status') == 'final' and g.get('result') in {'W', 'L'}:
            if g.get('result') == 'W':
                okc_wins += 1
            else:
                opp_wins += 1
        if str(g.get('game_id') or '') == target_id:
            break

    if okc_wins == opp_wins:
        return f'Series tied {okc_wins}-{opp_wins}'
    if okc_wins > opp_wins:
        return f'OKC leads {okc_wins}-{opp_wins} in series'
    return f'OKC trails {okc_wins}-{opp_wins} in series'
