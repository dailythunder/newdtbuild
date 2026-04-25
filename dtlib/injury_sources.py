from __future__ import annotations

from typing import Any, Dict, List

import requests

from .espn_sources import codes_match, format_injury, parse_espn_summary, safe_str

ESPN_INJURIES_URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries'

_INJURIES_CACHE: Dict[str, Any] = {}


def _meaningful(values: List[str]) -> List[str]:
    return [v for v in values if isinstance(v, str) and v.strip() and v.strip().upper() != 'TBD']


def fetch_espn_injuries() -> Dict[str, Any]:
    if _INJURIES_CACHE.get('data') is not None:
        return _INJURIES_CACHE['data']

    response = requests.get(
        ESPN_INJURIES_URL,
        timeout=20,
        headers={'User-Agent': 'DailyThunderBot/1.0'},
    )
    if response.status_code != 200:
        raise RuntimeError(f'ESPN injuries request failed: {response.status_code} {ESPN_INJURIES_URL}')

    data = response.json()
    _INJURIES_CACHE['data'] = data
    return data


def injury_team_tricode(team_obj: Dict[str, Any]) -> str:
    team = team_obj.get('team', {}) or {}
    return safe_str(
        team.get('abbreviation')
        or team_obj.get('abbreviation')
        or team.get('shortName')
        or team_obj.get('shortName')
    ).upper()


def injury_team_display_name(team_obj: Dict[str, Any]) -> str:
    return safe_str(team_obj.get('displayName') or (team_obj.get('team') or {}).get('displayName'))


def get_team_injuries(tricode: str, display_name: str = '') -> List[str]:
    data = fetch_espn_injuries()
    team_blocks = data.get('injuries') or []

    match = None
    for team in team_blocks:
        if codes_match(injury_team_tricode(team), tricode):
            match = team
            break

    if not match and display_name:
        for team in team_blocks:
            if injury_team_display_name(team) == display_name:
                match = team
                break

    if not match:
        print(f'Injuries team not found for {tricode} / {display_name}')
        return []

    out = []
    for inj in match.get('injuries') or []:
        line = format_injury(inj)
        if line:
            out.append(line)
    return out


def _summary_injuries(game: Dict[str, Any]) -> tuple[List[str], List[str]]:
    event_id = safe_str((game.get('source_ids') or {}).get('espn_event_id'))
    if not event_id:
        return [], []

    summary = parse_espn_summary(event_id)
    injuries_by_team = summary.get('injuries_by_team') or {}
    okc = injuries_by_team.get('OKC') or []

    opp_code = safe_str(game.get('opponent_abbr')).upper()
    opp = injuries_by_team.get(opp_code) or []
    if not opp:
        for tri, values in injuries_by_team.items():
            if codes_match(tri, opp_code):
                opp = values
                break

    return _meaningful(okc), _meaningful(opp)


def _global_injuries(game: Dict[str, Any]) -> tuple[List[str], List[str]]:
    okc = _meaningful(get_team_injuries('OKC', 'Oklahoma City Thunder'))
    opp = _meaningful(
        get_team_injuries(
            safe_str(game.get('opponent_abbr')).upper(),
            safe_str(game.get('opponent_full_name')),
        )
    )
    return okc, opp


def refresh_game_injuries(game: Dict[str, Any]) -> bool:
    library = game.setdefault('library', {})
    if not isinstance(library.get('okc_injuries'), list):
        library['okc_injuries'] = []
    if not isinstance(library.get('opp_injuries'), list):
        library['opp_injuries'] = []

    changed = False
    found_meaningful = False

    try:
        okc_summary, opp_summary = _summary_injuries(game)
        if okc_summary or opp_summary:
            found_meaningful = True
            if okc_summary and library.get('okc_injuries') != okc_summary:
                library['okc_injuries'] = okc_summary
                changed = True
            if opp_summary and library.get('opp_injuries') != opp_summary:
                library['opp_injuries'] = opp_summary
                changed = True
    except Exception as exc:
        print(f'ESPN summary injuries failed for {game.get("game_id")}: {exc}')

    if not found_meaningful:
        try:
            okc_global, opp_global = _global_injuries(game)
            if okc_global or opp_global:
                found_meaningful = True
                if okc_global and library.get('okc_injuries') != okc_global:
                    library['okc_injuries'] = okc_global
                    changed = True
                if opp_global and library.get('opp_injuries') != opp_global:
                    library['opp_injuries'] = opp_global
                    changed = True
        except Exception as exc:
            print(f'ESPN global injuries failed for {game.get("game_id")}: {exc}')

    if found_meaningful:
        print(
            'Injury refresh: '
            f"{game.get('game_id')} OKC={len(_meaningful(library.get('okc_injuries') or []))} "
            f"OPP={len(_meaningful(library.get('opp_injuries') or []))}"
        )
    else:
        print(f'Injury refresh skipped/no data for {game.get("game_id")}')

    return found_meaningful and changed
