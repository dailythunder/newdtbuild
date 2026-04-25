from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import requests


NBA_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json,text/html,application/xhtml+xml',
    'Referer': 'https://www.nba.com/',
}

ESPN_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Referer': 'https://www.espn.com/',
}

ESPN_TEAM_IDS = {
    'ATL': '1',
    'BOS': '2',
    'BKN': '17',
    'CHA': '30',
    'CHI': '4',
    'CLE': '5',
    'DAL': '6',
    'DEN': '7',
    'DET': '8',
    'GSW': '9',
    'HOU': '10',
    'IND': '11',
    'LAC': '12',
    'LAL': '13',
    'MEM': '29',
    'MIA': '14',
    'MIL': '15',
    'MIN': '16',
    'NOP': '3',
    'NYK': '18',
    'OKC': '25',
    'ORL': '19',
    'PHI': '20',
    'PHX': '21',
    'POR': '22',
    'SAC': '23',
    'SAS': '24',
    'TOR': '28',
    'UTA': '26',
    'WAS': '27',
}


def _normalize_status(raw: Optional[str]) -> str:
    text = (raw or '').strip()
    if not text:
        return 'GTD'
    lowered = text.lower()
    aliases = {
        'out': 'OUT',
        'questionable': 'GTD',
        'probable': 'PROB',
        'doubtful': 'DOU',
        'day-to-day': 'GTD',
        'game time decision': 'GTD',
        'game-time decision': 'GTD',
        'out for season': 'OFS',
    }
    return aliases.get(lowered, text.upper())


def _format_entry(name: str, status: Optional[str], reason: Optional[str]) -> Optional[str]:
    clean_name = (name or '').strip()
    if not clean_name:
        return None
    clean_status = _normalize_status(status)
    clean_reason = (reason or '').strip()
    if clean_reason:
        return f'{clean_name} - {clean_status} ({clean_reason})'
    return f'{clean_name} - {clean_status}'


def _meaningful(values: List[str]) -> List[str]:
    return [v for v in values if isinstance(v, str) and v.strip() and v.strip().upper() != 'TBD']


def _parse_nba_items(items: List[dict]) -> List[str]:
    out: List[str] = []
    for item in items or []:
        entry = _format_entry(
            item.get('playerName') or item.get('name') or item.get('player'),
            item.get('status') or item.get('availability'),
            item.get('reason') or item.get('injury') or item.get('comment'),
        )
        if entry:
            out.append(entry)
    return out


def _nba_game_injuries(game_id: str) -> Optional[Tuple[List[str], List[str]]]:
    candidates = [
        f'https://cdn.nba.com/static/json/liveData/injuryReport/injuryReport_{game_id}.json',
        f'https://cdn.nba.com/static/json/liveData/injuryreport/injuryReport_{game_id}.json',
    ]
    for url in candidates:
        try:
            response = requests.get(url, headers=NBA_HEADERS, timeout=20)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
            root = payload.get('injuryReport') if isinstance(payload, dict) else None
            root = root if isinstance(root, dict) else payload
            okc_items = root.get('okc') or root.get('okcInjuries') or root.get('thunder') or root.get('home') or []
            opp_items = root.get('opp') or root.get('oppInjuries') or root.get('opponent') or root.get('away') or []
            okc = _parse_nba_items(okc_items)
            opp = _parse_nba_items(opp_items)
            if _meaningful(okc) or _meaningful(opp):
                return okc, opp
        except Exception as exc:  # noqa: PERF203
            print(f'NBA injury source unavailable for {game_id}: {exc}')
    return None


def _espn_team_injuries(team_abbr: Optional[str]) -> List[str]:
    tid = ESPN_TEAM_IDS.get((team_abbr or '').upper())
    if not tid:
        return []
    url = f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{tid}/injuries'
    response = requests.get(url, headers=ESPN_HEADERS, timeout=20)
    response.raise_for_status()
    payload = response.json()
    out: List[str] = []
    for item in payload.get('injuries', []) or []:
        athlete = item.get('athlete') or {}
        status = item.get('status') or {}
        detail = item.get('details') or {}
        entry = _format_entry(
            athlete.get('displayName') or athlete.get('shortName'),
            status.get('shortDetail') or status.get('description') or status.get('name'),
            detail.get('type') or detail.get('detail') or detail.get('description'),
        )
        if entry:
            out.append(entry)
    return out


def _espn_game_injuries(game: Dict) -> Optional[Tuple[List[str], List[str]]]:
    okc = _espn_team_injuries('OKC')
    opp = _espn_team_injuries(game.get('opponent_abbr'))
    if _meaningful(okc) or _meaningful(opp):
        return okc, opp
    return None


def refresh_game_injuries(game: Dict) -> bool:
    game_id = str(game.get('game_id') or '').strip()
    library = game.setdefault('library', {})
    if not isinstance(library.get('okc_injuries'), list):
        library['okc_injuries'] = []
    if not isinstance(library.get('opp_injuries'), list):
        library['opp_injuries'] = []

    if not game_id:
        print('Injury refresh skipped/no data for unknown-game')
        return False

    try:
        source = _nba_game_injuries(game_id)
        if source is None:
            source = _espn_game_injuries(game)
        if source is None:
            print(f'Injury refresh skipped/no data for {game_id}')
            return False

        okc, opp = source
        okc_clean = _meaningful(okc)
        opp_clean = _meaningful(opp)
        if not (okc_clean or opp_clean):
            print(f'Injury refresh skipped/no data for {game_id}')
            return False

        library['okc_injuries'] = okc_clean
        library['opp_injuries'] = opp_clean
        print(
            'Injury refresh: found '
            f'{len(okc_clean)} OKC / {len(opp_clean)} {game.get("opponent_abbr") or "OPP"} entries for {game_id}'
        )
        return True
    except Exception as exc:
        print(f'Injury refresh failed for {game_id}: {exc}')
        return False
