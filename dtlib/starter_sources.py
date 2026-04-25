from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import requests

from .espn_sources import codes_match, safe_str

CT_TZ = ZoneInfo('America/Chicago')
ROTOWIRE_LINEUPS_URL = 'https://www.rotowire.com/basketball/nba-lineups.php'
NBA_SCHEDULE_URL = 'https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json'


def _meaningful(values: List[str]) -> List[str]:
    return [v for v in values if isinstance(v, str) and v.strip() and v.strip().upper() != 'TBD']


def _is_complete(values: List[str]) -> bool:
    return len(_meaningful(values)) == 5


def rotowire_extract_team(block: str, side_class: str) -> str:
    match = re.search(
        rf'<a[^>]+class="lineup__team {side_class}"[^>]*>.*?<div class="lineup__abbr">(.*?)</div>',
        block,
        re.S,
    )
    if match:
        return unescape(match.group(1)).strip().upper()
    return ''


def extract_ul_block(block: str, side_class: str) -> str:
    for match in re.finditer(r'<ul[^>]*>', block):
        tag = match.group(0)
        class_match = re.search(r'class=["\']([^"\']+)["\']', tag)
        if not class_match:
            continue
        classes = class_match.group(1).split()
        if 'lineup__list' in classes and side_class in classes:
            ul_start = match.start()
            ul_end = block.find('</ul>', match.end())
            if ul_end == -1:
                return ''
            return block[ul_start:ul_end + len('</ul>')]
    return ''


def rotowire_extract_players(block: str, side_class: str) -> List[str]:
    ul = extract_ul_block(block, side_class)
    if not ul:
        return []

    candidates = []
    seen = set()
    in_expected = False

    for li in re.finditer(r'<li[^>]*class=["\'][^"\']+["\'][^>]*>.*?</li>', ul, flags=re.S):
        li_html = li.group(0)

        if 'lineup__status' in li_html and ('is-expected' in li_html or 'is-confirmed' in li_html):
            in_expected = True
            continue

        if 'lineup__title' in li_html and in_expected:
            break

        if not in_expected:
            continue

        if 'lineup__player' not in li_html or 'is-ofs' in li_html:
            continue

        title_match = re.search(r'<a[^>]+title=["\']([^"\']+)["\']', li_html)
        name = unescape(title_match.group(1)).strip() if title_match else ''
        if not name:
            text_match = re.search(r'>\s*([^<]+)\s*</a>', li_html)
            name = unescape(text_match.group(1)).strip() if text_match else ''

        if name and name not in seen:
            seen.add(name)
            candidates.append({'name': name, 'html': li_html, 'order': len(candidates)})

    if len(candidates) <= 5:
        return [c['name'] for c in candidates]

    def candidate_score(candidate: Dict[str, Any]) -> tuple[int, int]:
        html = candidate['html']
        score = 0
        if 'is-confirmed' in html:
            score += 100
        if 'is-expected' in html:
            score += 50
        if 'is-pct-play-100' in html:
            score += 30
        elif 'is-pct-play-75' in html:
            score += 20
        elif 'is-pct-play-50' in html:
            score += 10
        if 'has-injury-status' in html and re.search(r'\bOut\b', unescape(html)):
            score -= 20
        return score, -candidate['order']

    top = sorted(candidates, key=candidate_score, reverse=True)[:5]
    return [c['name'] for c in top]


def fetch_rotowire_lineups() -> Dict[str, List[str]]:
    response = requests.get(
        ROTOWIRE_LINEUPS_URL,
        timeout=20,
        headers={'User-Agent': 'DailyThunderBot/1.0'},
    )
    response.raise_for_status()
    html = response.text

    lineups: Dict[str, List[str]] = {}
    blocks = html.split('<div class="lineup is-nba"')

    for part in blocks[1:]:
        block = '<div class="lineup is-nba"' + part
        visit = rotowire_extract_team(block, 'is-visit')
        home = rotowire_extract_team(block, 'is-home')

        if visit:
            lineups[visit] = rotowire_extract_players(block, 'is-visit')
        if home:
            lineups[home] = rotowire_extract_players(block, 'is-home')

    return lineups


def fetch_last_completed_gameid(team_tricode: str) -> str:
    response = requests.get(
        NBA_SCHEDULE_URL,
        timeout=15,
        headers={'User-Agent': 'DailyThunderBot/1.0'},
    )
    response.raise_for_status()
    data = response.json()

    games = []
    now = datetime.now(tz=CT_TZ)

    for block in data.get('leagueSchedule', {}).get('gameDates', []):
        for game in block.get('games', []):
            home = game.get('homeTeam', {}) or {}
            away = game.get('awayTeam', {}) or {}
            if home.get('teamTricode') == team_tricode or away.get('teamTricode') == team_tricode:
                dt_utc = game.get('gameDateTimeUTC') or ''
                try:
                    dt = datetime.fromisoformat(dt_utc.replace('Z', '+00:00')).astimezone(CT_TZ)
                except Exception:
                    continue
                gid = safe_str(game.get('gameId')).zfill(10)
                games.append((dt, gid))

    games.sort(key=lambda t: t[0])
    past = [t for t in games if t[0] < now]
    if not past:
        raise RuntimeError(f'No completed games found yet for {team_tricode}.')
    return past[-1][1]


def fetch_last_game_starters(team_tricode: str) -> List[str]:
    gid = fetch_last_completed_gameid(team_tricode)
    url = f'https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gid}.json'

    response = requests.get(
        url,
        timeout=15,
        headers={'User-Agent': 'DailyThunderBot/1.0'},
    )
    response.raise_for_status()
    data = response.json()

    players = []
    for side in ('homeTeam', 'awayTeam'):
        team = data.get('game', {}).get(side, {}) or {}
        if safe_str(team.get('teamTricode')).upper() == team_tricode:
            for player in team.get('players', []) or []:
                if str(player.get('starter', '0')) == '1':
                    name = safe_str(player.get('name')) or (
                        safe_str(player.get('firstName')) + ' ' + safe_str(player.get('familyName'))
                    ).strip()
                    if name:
                        players.append(name)
            break

    if len(players) == 5:
        return players

    raise RuntimeError(
        f'Could not determine exactly 5 starters for {team_tricode} from last boxscore (found {len(players)}).'
    )


def _find_rotowire_starters(lineups: Dict[str, List[str]], code: str) -> List[str]:
    wanted = safe_str(code).upper()
    for tri, players in lineups.items():
        if codes_match(tri, wanted):
            return _meaningful(players)
    return []


def _write_starters_if_complete(library: Dict[str, Any], key: str, starters: List[str]) -> bool:
    cleaned = _meaningful(starters)
    if len(cleaned) != 5:
        return False
    if library.get(key) == cleaned:
        return False
    library[key] = cleaned
    return True


def refresh_game_starters(game: Dict[str, Any]) -> bool:
    library = game.setdefault('library', {})
    if not isinstance(library.get('okc_likely_starters'), list):
        library['okc_likely_starters'] = []
    if not isinstance(library.get('opp_likely_starters'), list):
        library['opp_likely_starters'] = []

    changed = False
    found = False

    opp_code = safe_str(game.get('opponent_abbr')).upper()

    try:
        lineups = fetch_rotowire_lineups()
        okc_rw = _find_rotowire_starters(lineups, 'OKC')
        opp_rw = _find_rotowire_starters(lineups, opp_code)

        if _is_complete(okc_rw):
            found = True
            changed = _write_starters_if_complete(library, 'okc_likely_starters', okc_rw) or changed
        if _is_complete(opp_rw):
            found = True
            changed = _write_starters_if_complete(library, 'opp_likely_starters', opp_rw) or changed
    except Exception as exc:
        print(f'Rotowire starters failed for {game.get("game_id")}: {exc}')

    try:
        if not _is_complete(library.get('okc_likely_starters') or []):
            okc_last = fetch_last_game_starters('OKC')
            if _is_complete(okc_last):
                found = True
                changed = _write_starters_if_complete(library, 'okc_likely_starters', okc_last) or changed

        if opp_code and not _is_complete(library.get('opp_likely_starters') or []):
            opp_last = fetch_last_game_starters(opp_code)
            if _is_complete(opp_last):
                found = True
                changed = _write_starters_if_complete(library, 'opp_likely_starters', opp_last) or changed
    except Exception as exc:
        print(f'NBA starter fallback failed for {game.get("game_id")}: {exc}')

    if found:
        print(
            'Starter refresh: '
            f"{game.get('game_id')} OKC={len(_meaningful(library.get('okc_likely_starters') or []))} "
            f"OPP={len(_meaningful(library.get('opp_likely_starters') or []))}"
        )
    else:
        print(f'Starter refresh skipped/no data for {game.get("game_id")}')

    return found and changed
