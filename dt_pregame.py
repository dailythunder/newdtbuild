import os
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_pregame_html
from dtlib.state_io import load_all, save_all
from dtlib.utils import is_abs_http_url, parse_iso, slugify, utcnow, utcnow_iso

WINDOWS = {6, 5, 4, 3, 2, 1}
DEMO_GAME_ID = '0042500143'
DEMO_HERO_IMAGE = 'https://storage.ghost.io/c/f2/f9/f2f98597-fc28-4a31-8135-86802fa12f06/content/images/2026/04/0042500143.png'
DEMO_MATRIX_IMAGE = 'https://storage.ghost.io/c/f2/f9/f2f98597-fc28-4a31-8135-86802fa12f06/content/images/size/w1600/2026/04/THUNDER-SUNS-MATCHUP-MATRIX.png'
LOCKED_EXCERPT = "All the essentials for the Thunder's Round 1 matchup: tip & broadcast info, lineups, and live thread."


def _is_demo_mode() -> bool:
    return str(os.getenv('DT_FORCE_DEMO', '')).strip().lower() == 'true'


def _get_game_by_id(games: List[Dict], game_id: Optional[str]) -> Optional[Dict]:
    if not game_id:
        return None
    for game in games:
        if str(game.get('game_id') or '').strip() == str(game_id).strip():
            return game
    return None


def _format_date(local_date: Optional[str]) -> str:
    if not local_date:
        return 'TBD'
    try:
        dt = datetime.strptime(local_date, '%Y-%m-%d')
        return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    except ValueError:
        return local_date


def _format_tip_ct(tipoff_utc: Optional[str]) -> str:
    tip = parse_iso(tipoff_utc)
    if not tip:
        return 'TBD'
    ct = tip.astimezone(ZoneInfo('America/Chicago'))
    hour = ct.strftime('%I').lstrip('0') or '0'
    return f"{hour}:{ct.strftime('%M %p')} CT"


def _opponent_header(game: Dict) -> str:
    return (
        game.get('opponent_abbr')
        or game.get('opponent_full_name')
        or game.get('opponent')
        or 'Opponent'
    )


def _series_status(games: List[Dict], game: Dict) -> str:
    okc_wins = 0
    opp_wins = 0
    opponent = game.get('opponent')
    series_round = game.get('series_round')
    for g in sorted(games, key=lambda x: x.get('tipoff_utc') or ''):
        if g.get('season_phase') != 'playoffs':
            continue
        if g.get('opponent') != opponent or g.get('series_round') != series_round:
            continue
        if g.get('status') == 'final' and g.get('result') in {'W', 'L'}:
            if g.get('result') == 'W':
                okc_wins += 1
            else:
                opp_wins += 1
    if okc_wins == opp_wins:
        return f'Series tied {okc_wins}-{opp_wins}'
    if okc_wins > opp_wins:
        return f'OKC leads {okc_wins}-{opp_wins}'
    return f'OKC trails {okc_wins}-{opp_wins}'


def _best_last_known_starters(games: List[Dict], key: str) -> List[str]:
    for g in sorted(games, key=lambda x: x.get('tipoff_utc') or '', reverse=True):
        starters = g.get('library', {}).get(key) or []
        filtered = [s for s in starters if isinstance(s, str) and s.strip() and s.strip().upper() != 'TBD']
        if len(filtered) >= 5:
            return filtered[:5]
    return []


def _pad_starters(values: List[str]) -> List[str]:
    clean = [v for v in values if isinstance(v, str) and v.strip()]
    return (clean + ['TBD'] * 5)[:5]


def _ensure_demo_game(games: List[Dict], game_id: str, season_config: dict, series_config: dict) -> Dict:
    existing = _get_game_by_id(games, game_id)
    if existing:
        return existing

    base = games[-1] if games else {}
    base_library = base.get('library', {}) if isinstance(base.get('library'), dict) else {}
    return {
        'season_phase': 'playoffs',
        'series_round': 'R1',
        'game_number_in_series': 3,
        'game_id': game_id,
        'opponent': 'Suns',
        'opponent_full_name': 'Phoenix Suns',
        'home_away': 'away',
        'local_date': '2026-04-25',
        'tipoff_utc': base.get('tipoff_utc') or '2026-04-26T00:30:00Z',
        'status': 'scheduled',
        'result': None,
        'thunder_score': None,
        'opponent_score': None,
        'links': {},
        'library': {
            'tv': base_library.get('tv') or 'TBD',
            'line': base_library.get('line') or 'TBD',
            'location': base_library.get('location') or 'Footprint Center, Phoenix',
            'feature_image_src': DEMO_HERO_IMAGE,
            'feature_image_srcset': None,
            'matchup_matrix_src': DEMO_MATRIX_IMAGE,
            'matchup_matrix_srcset': None,
            'okc_injuries': base_library.get('okc_injuries') or [],
            'opp_injuries': base_library.get('opp_injuries') or [],
            'okc_likely_starters': _best_last_known_starters(games, 'okc_likely_starters'),
            'opp_likely_starters': _best_last_known_starters(games, 'opp_likely_starters'),
        },
        'assets': {'game_image': DEMO_HERO_IMAGE, 'scoreboard_image': None},
        'automation': {'pregame_slug': None},
        'timestamps': {'last_verified_utc': None},
    }


def _hero_image(game: dict, season_config: dict, series_config: dict, force_demo: bool) -> Optional[str]:
    game_id = game.get('game_id')
    url = game.get('assets', {}).get('game_image') or game.get('library', {}).get('feature_image_src')
    if not url:
        pattern = season_config.get('asset_patterns', {}).get('game_image') or series_config.get('asset_patterns', {}).get('game_image')
        if pattern and game_id:
            url = pattern.format(game_id=game_id)
    if force_demo and game_id == DEMO_GAME_ID and not url:
        url = DEMO_HERO_IMAGE
    return url if is_abs_http_url(url) else None


def _matchup_matrix(game: dict, season_config: dict, series_config: dict, force_demo: bool) -> Optional[str]:
    game_id = game.get('game_id')
    matrix = game.get('library', {}).get('matchup_matrix_src')
    if not matrix:
        pattern = season_config.get('asset_patterns', {}).get('matchup_matrix_image') or series_config.get('asset_patterns', {}).get('matchup_matrix_image')
        if pattern:
            matrix = pattern.format(game_id=game_id) if '{game_id}' in pattern and game_id else pattern
    if force_demo and game_id == DEMO_GAME_ID and not matrix:
        matrix = DEMO_MATRIX_IMAGE
    return matrix if is_abs_http_url(matrix) else None


def eligible_game(
    games: List[Dict],
    *,
    target_game_id: Optional[str] = None,
    force_demo: bool = False,
    season_config: Optional[dict] = None,
    series_config: Optional[dict] = None,
) -> Optional[dict]:
    if force_demo and target_game_id:
        if target_game_id == DEMO_GAME_ID:
            return _ensure_demo_game(games, target_game_id, season_config or {}, series_config or {})
        return _get_game_by_id(games, target_game_id)

    now = utcnow()
    candidates = []
    for game in games:
        tip = parse_iso(game.get('tipoff_utc'))
        if not tip or game.get('status') == 'final':
            continue
        hours = int(round((tip - now).total_seconds() / 3600.0))
        if hours in WINDOWS:
            candidates.append((tip, game))
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1] if candidates else None


def main() -> None:
    data = load_all()
    games = data['season_state'].get('games', [])
    force_demo = _is_demo_mode()
    target_game_id = os.getenv('DT_TARGET_GAME_ID', '').strip() or None

    game = eligible_game(
        games,
        target_game_id=target_game_id,
        force_demo=force_demo,
        season_config=data.get('season_config', {}),
        series_config=data.get('series_config', {}),
    )
    if not game:
        print('No eligible pregame window.')
        return

    opponent = game.get('opponent') or 'Opponent'
    if game.get('season_phase') == 'playoffs' and game.get('game_number_in_series'):
        game_number = game.get('game_number_in_series') or '?'
        matchup_label = '@' if str(game.get('home_away') or '').lower() == 'away' else 'vs.'
        title = f"Game {game_number} Pregame Primer: Thunder {matchup_label} {opponent}"
        custom_excerpt = LOCKED_EXCERPT
    else:
        title = f'Pregame Primer: Thunder vs. {opponent}'
        location = game.get('library', {}).get('location')
        custom_excerpt = _format_date(game.get('local_date'))
        if location:
            custom_excerpt += f' • {location}'

    game.setdefault('library', {})['okc_likely_starters'] = _pad_starters(
        game.get('library', {}).get('okc_likely_starters') or _best_last_known_starters(games, 'okc_likely_starters')
    )
    game.setdefault('library', {})['opp_likely_starters'] = _pad_starters(
        game.get('library', {}).get('opp_likely_starters') or _best_last_known_starters(games, 'opp_likely_starters')
    )
    game['library']['feature_image_src'] = _hero_image(game, data.get('season_config', {}), data.get('series_config', {}), force_demo)
    game['library']['matchup_matrix_src'] = _matchup_matrix(game, data.get('season_config', {}), data.get('series_config', {}), force_demo)

    game['render_context'] = {
        'date_display': _format_date(game.get('local_date')),
        'tip_display': _format_tip_ct(game.get('tipoff_utc')),
        'series_status': _series_status(games, game),
        'opp_header': _opponent_header(game),
    }

    slug = game.get('automation', {}).get('pregame_slug') or slugify(f"pregame {game.get('game_id') or game.get('local_date')} {opponent}")
    html = build_pregame_html(game, data.get('season_config', {}))
    ghost = GhostClient()
    existing = ghost.find_post_by_slug(slug) if ghost.enabled else None
    if existing and existing.get('status') == 'published':
        print(f'Pregame already published, skipping: {slug}')
        return

    tags = ['pregame primer', 'thunder pregame', 'thunder suns'] if force_demo and (game.get('game_id') == DEMO_GAME_ID) else ['pregame primer', 'thunder pregame', f"thunder {opponent.lower()}"]

    post = ghost.upsert_draft(
        title=title,
        slug=slug,
        html=html,
        tags=tags,
        feature_image=game['library'].get('feature_image_src'),
        custom_excerpt=custom_excerpt,
        visibility='members',
        featured=False,
        update_if_unpublished=True,
    )

    if post.get('id') == 'dry-run':
        print('Pregame dry-run only; not mutating state.')
        print(f'TITLE={title}')
        print(f'EXCERPT={custom_excerpt}')
        print(f'TAGS={tags}')
        return

    persisted_game = _get_game_by_id(games, game.get('game_id'))
    if persisted_game is not None:
        persisted_game.setdefault('automation', {})['pregame_slug'] = slug
    data['content_state'].setdefault('ghost_posts', {})[slug] = {
        'id': post.get('id'),
        'lane': 'pregame',
        'updated_utc': utcnow_iso(),
    }
    save_all(data)
    print(f'Pregame upserted: {slug}')


if __name__ == '__main__':
    main()
