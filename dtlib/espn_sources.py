from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import requests

CT_TZ = ZoneInfo('America/Chicago')
ESPN_SUMMARY_URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='
ESPN_OKC_SCHEDULE_URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/okc/schedule'

TRI_ALIASES = {
    'SA': {'SA', 'SAS'},
    'SAS': {'SA', 'SAS'},
    'GS': {'GS', 'GSW'},
    'GSW': {'GS', 'GSW'},
    'PHX': {'PHX', 'PHO'},
    'PHO': {'PHX', 'PHO'},
    'UTAH': {'UTAH', 'UTA'},
    'UTA': {'UTAH', 'UTA'},
    'NO': {'NO', 'NOP'},
    'NOP': {'NO', 'NOP'},
    'NY': {'NY', 'NYK'},
    'NYK': {'NY', 'NYK'},
    'WSH': {'WSH', 'WAS'},
    'WAS': {'WSH', 'WAS'},
}


OKC_TRICODE = 'OKC'


def safe_str(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def code_variants(code: str) -> set[str]:
    raw = safe_str(code).upper()
    return TRI_ALIASES.get(raw, {raw})


def codes_match(a: str, b: str) -> bool:
    return bool(code_variants(a) & code_variants(b))


def http_get(url: str, stage: str, timeout: int = 20) -> requests.Response:
    response = requests.get(url, timeout=timeout, headers={'User-Agent': 'DailyThunderBot/1.0'})
    print(f'HTTP {stage}: {response.status_code} {url}')
    response.raise_for_status()
    return response


def format_injury(inj: Dict[str, Any], status: Optional[str] = None) -> str:
    athlete = inj.get('athlete', {}) or {}
    name = safe_str(athlete.get('displayName') or athlete.get('fullName'))

    details = inj.get('details', {}) or {}

    if status is None:
        status = safe_str((details.get('fantasyStatus') or {}).get('description'))
        if not status:
            status = safe_str(inj.get('status'))

    side_part = safe_str(details.get('side'))
    type_part = safe_str(details.get('type'))
    detail_part = safe_str(details.get('detail'))

    detail_bits = []
    if side_part and side_part.lower() != 'not specified':
        detail_bits.append(side_part)
    for part in (type_part, detail_part):
        if part:
            detail_bits.append(part)

    if detail_bits:
        return f"{name} - {status} ({' '.join(detail_bits)})".strip()
    return f'{name} - {status}'.strip()


def fetch_espn_summary(event_id: str) -> Dict[str, Any]:
    url = f'{ESPN_SUMMARY_URL}{event_id}'
    response = http_get(url, 'fetch_espn_summary', timeout=20)
    return response.json()


def parse_espn_summary(event_id: str) -> Dict[str, Any]:
    data = fetch_espn_summary(event_id)

    header = data.get('header', {}) or {}
    comp = (header.get('competitions') or [{}])[0]
    competitors = comp.get('competitors') or []

    okc = next((c for c in competitors if (c.get('team') or {}).get('abbreviation') == OKC_TRICODE), None)
    opp = next((c for c in competitors if c is not okc), None)

    dt_raw = comp.get('date') or header.get('date') or ''
    dt_ct = None
    if dt_raw:
        try:
            dt_ct = datetime.fromisoformat(dt_raw.replace('Z', '+00:00')).astimezone(CT_TZ)
        except Exception:
            dt_ct = None

    def record_summary(comp_obj: Optional[Dict[str, Any]]) -> str:
        for rec in (comp_obj or {}).get('record') or []:
            if rec.get('type') == 'total':
                return safe_str(rec.get('summary') or rec.get('displayValue'))
        return ''

    broadcasts = data.get('broadcasts') or comp.get('broadcasts') or []
    tv_names = []
    for bcast in broadcasts:
        name = safe_str((bcast.get('media') or {}).get('shortName') or bcast.get('station'))
        if name:
            tv_names.append(name)
    tv = ', '.join(sorted(set(tv_names)))

    odds = data.get('pickcenter') or data.get('odds') or []
    spread = safe_str(odds[0].get('details')) if odds else ''

    game_info = data.get('gameInfo', {}) or {}
    venue = safe_str((game_info.get('venue') or {}).get('fullName'))

    injuries_by_team: Dict[str, list[str]] = {}
    for team_block in data.get('injuries') or []:
        team = team_block.get('team', {}) or {}
        tri = safe_str(team.get('abbreviation')).upper()
        injuries = []
        for inj in team_block.get('injuries') or []:
            line = format_injury(inj)
            if line:
                injuries.append(line)
        if tri:
            injuries_by_team[tri] = injuries

    game_url = ''
    for link in header.get('links', []) or []:
        rel = link.get('rel') or []
        if 'summary' in rel or 'event' in rel:
            game_url = safe_str(link.get('href'))
            if game_url:
                break

    home_comp = next((c for c in competitors if c.get('homeAway') == 'home'), {}) or {}
    away_comp = next((c for c in competitors if c.get('homeAway') == 'away'), {}) or {}
    home_team = home_comp.get('team', {}) or {}
    away_team = away_comp.get('team', {}) or {}
    opp_team = (opp or {}).get('team', {}) or {}

    return {
        'espn_event_id': safe_str(event_id),
        'espn_game_url': game_url,
        'date': dt_ct.date().isoformat() if dt_ct else '',
        'tipoff_utc': dt_raw,
        'time_ct': dt_ct.strftime('%I:%M %p').lstrip('0') if dt_ct else '',
        'location': venue,
        'tv': tv,
        'line': spread,
        'okc_record': record_summary(okc) if okc else '',
        'opp_record': record_summary(opp) if opp else '',
        'injuries_by_team': injuries_by_team,
        'home_tricode': safe_str(home_team.get('abbreviation')).upper(),
        'away_tricode': safe_str(away_team.get('abbreviation')).upper(),
        'home_name': safe_str(home_team.get('displayName')),
        'away_name': safe_str(away_team.get('displayName')),
        'opponent_abbr': safe_str(opp_team.get('abbreviation')).upper(),
        'opponent_full_name': safe_str(opp_team.get('displayName')),
        'opponent': safe_str(opp_team.get('shortDisplayName') or opp_team.get('name')),
    }


def _parse_event_id_from_url(url: str) -> str:
    for token in reversed(safe_str(url).split('/')):
        token = token.strip()
        if token.isdigit() and len(token) >= 6:
            return token
    return ''


def _is_away_game(game: Dict[str, Any]) -> bool:
    return safe_str(game.get('home_away')).lower() == 'away'


def season_year_for(date_value: datetime) -> int:
    return date_value.year + 1 if date_value.month >= 7 else date_value.year


def fetch_espn_okc_events(start_date: datetime, end_date: datetime, season_year: Optional[int] = None) -> Dict[tuple, Dict[str, Any]]:
    if season_year is None:
        season_year = season_year_for(start_date)

    url = f'{ESPN_OKC_SCHEDULE_URL}?seasontype=2&season={season_year}'
    response = requests.get(url, timeout=20, headers={'User-Agent': 'DailyThunderBot/1.0'})
    response.raise_for_status()
    data = response.json()

    events: Dict[tuple, Dict[str, Any]] = {}
    for ev in data.get('events', []) or []:
        comp = (ev.get('competitions') or [{}])[0]
        competitors = comp.get('competitors') or []

        okc = next((c for c in competitors if (c.get('team') or {}).get('abbreviation') == OKC_TRICODE), None)
        if not okc:
            continue

        opp = next((c for c in competitors if c is not okc), None)
        opp_team = (opp or {}).get('team', {}) or {}

        opp_tri = safe_str(opp_team.get('abbreviation')).upper()
        home_away = safe_str(okc.get('homeAway')).lower()
        away = home_away == 'away'

        event_dt = ev.get('date') or comp.get('date')
        if not event_dt:
            continue

        try:
            dt = datetime.fromisoformat(event_dt.replace('Z', '+00:00')).astimezone(CT_TZ)
        except Exception:
            continue

        if not (start_date.date() <= dt.date() <= end_date.date()):
            continue

        key = (dt.date().isoformat(), opp_tri, away)
        events[key] = {
            'espn_event_id': safe_str(ev.get('id')),
            'espn_date': event_dt,
            'opp_tricode': opp_tri,
            'opp_full': safe_str(opp_team.get('displayName')),
            'opp_nick': safe_str(opp_team.get('shortDisplayName') or opp_team.get('name')),
            'away': away,
        }

    return events


def _meaningful(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _set_if_meaningful(target: Dict[str, Any], key: str, value: Any) -> bool:
    if _meaningful(value) and target.get(key) != value:
        target[key] = value
        return True
    return False


def resolve_espn_event_id_for_game(game: Dict[str, Any]) -> Optional[str]:
    source_ids = game.setdefault('source_ids', {})
    links = game.setdefault('links', {})

    existing = safe_str(source_ids.get('espn_event_id'))
    if existing:
        return existing

    linked = _parse_event_id_from_url(links.get('espn_game') or '')
    if linked:
        source_ids['espn_event_id'] = linked
        return linked

    local_date = safe_str(game.get('local_date'))
    opp_code = safe_str(game.get('opponent_abbr')).upper()
    away = _is_away_game(game)
    if not local_date or not opp_code:
        return None

    try:
        center_date = datetime.strptime(local_date, '%Y-%m-%d').replace(tzinfo=CT_TZ)
    except ValueError:
        return None

    start = center_date - timedelta(days=2)
    end = center_date + timedelta(days=2)

    seasons = sorted({season_year_for(start), season_year_for(center_date), season_year_for(end)})

    for season in seasons:
        try:
            events = fetch_espn_okc_events(start, end, season_year=season)
        except Exception as exc:
            print(f'ESPN schedule fetch failed for season {season}: {exc}')
            continue

        for (event_date, event_opp, event_away), meta in events.items():
            if event_date != local_date:
                continue
            if event_away != away:
                continue
            if not codes_match(event_opp, opp_code):
                continue
            event_id = safe_str(meta.get('espn_event_id'))
            if event_id:
                source_ids['espn_event_id'] = event_id
                return event_id

    return None


def refresh_game_espn_context(game: Dict[str, Any]) -> bool:
    changed = False
    source_ids = game.setdefault('source_ids', {})
    links = game.setdefault('links', {})
    library = game.setdefault('library', {})

    event_id = resolve_espn_event_id_for_game(game)
    if not event_id:
        return False

    source_ids['espn_event_id'] = event_id

    try:
        summary = parse_espn_summary(event_id)
    except Exception as exc:
        print(f'ESPN summary refresh failed for {game.get("game_id")}: {exc}')
        return False

    changed = _set_if_meaningful(source_ids, 'espn_event_id', summary.get('espn_event_id')) or changed
    changed = _set_if_meaningful(links, 'espn_game', summary.get('espn_game_url')) or changed
    changed = _set_if_meaningful(game, 'tipoff_utc', summary.get('tipoff_utc')) or changed
    changed = _set_if_meaningful(game, 'local_date', summary.get('date')) or changed

    if not safe_str(game.get('opponent_abbr')):
        changed = _set_if_meaningful(game, 'opponent_abbr', summary.get('opponent_abbr')) or changed
    if not safe_str(game.get('opponent_full_name')):
        changed = _set_if_meaningful(game, 'opponent_full_name', summary.get('opponent_full_name')) or changed
    if not safe_str(game.get('opponent')):
        changed = _set_if_meaningful(game, 'opponent', summary.get('opponent')) or changed

    changed = _set_if_meaningful(library, 'tv', summary.get('tv')) or changed
    changed = _set_if_meaningful(library, 'line', summary.get('line')) or changed
    changed = _set_if_meaningful(library, 'location', summary.get('location')) or changed

    injuries_by_team = summary.get('injuries_by_team') or {}
    okc_inj = injuries_by_team.get(OKC_TRICODE) or []
    if isinstance(okc_inj, list) and okc_inj:
        if library.get('okc_injuries') != okc_inj:
            library['okc_injuries'] = okc_inj
            changed = True

    opp_key = safe_str(summary.get('opponent_abbr')).upper() or safe_str(game.get('opponent_abbr')).upper()
    opp_inj = injuries_by_team.get(opp_key) or []
    if isinstance(opp_inj, list) and opp_inj:
        if library.get('opp_injuries') != opp_inj:
            library['opp_injuries'] = opp_inj
            changed = True

    if changed:
        print(f'ESPN context refreshed for {game.get("game_id")}: event {event_id}')
    return changed
