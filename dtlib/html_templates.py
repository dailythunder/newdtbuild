from html import escape
from typing import Dict, List

from .utils import safe_str

TEAM_NAME = 'Oklahoma City Thunder'
PHOTOS_LINK = '<p style="text-align:center;"><a href="https://www.nba.com/thunder/photos">PHOTOS⚡THUNDER</a></p>'


def _row(label: str, value: str) -> str:
    return f'<tr><td><strong>{escape(label)}</strong></td><td>{escape(safe_str(value) or "TBD")}</td></tr>'


def _two_col_table(title_left: str, items_left: List[str], title_right: str, items_right: List[str]) -> str:
    left_rows = ''.join(f'<li>{escape(i)}</li>' for i in (items_left or ['TBD']))
    right_rows = ''.join(f'<li>{escape(i)}</li>' for i in (items_right or ['TBD']))
    return (
        '<div class="kg-card kg-html-card"><div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;">'
        f'<div><h3>{escape(title_left)}</h3><ul>{left_rows}</ul></div>'
        f'<div><h3>{escape(title_right)}</h3><ul>{right_rows}</ul></div>'
        '</div></div>'
    )


def _official_links(game: Dict) -> str:
    links = game.get('links', {})
    out = []
    if links.get('nba_pbp'):
        out.append(f'<a href="{escape(links["nba_pbp"])}">NBA Play-by-Play</a>')
    if links.get('courtsketch'):
        out.append(f'<a href="{escape(links["courtsketch"])}">CourtSketch</a>')
    if not out:
        return ''
    return '<p style="text-align:center;">' + ' | '.join(out) + '</p>'


def build_pregame_html(game: Dict, season_config: Dict) -> str:
    lib = game.get('library', {})
    opponent = game.get('opponent') or 'Opponent'
    game_context = ''
    if game.get('season_phase') == 'playoffs' and game.get('game_number_in_series'):
        round_label = season_config.get('round_label') or game.get('series_round') or 'Playoffs'
        game_context = f'{round_label}, Game {game.get("game_number_in_series")}'

    location = lib.get('location') or 'TBD'
    local_date = game.get('local_date') or 'TBD'
    tipoff = game.get('tipoff_utc') or 'TBD'
    tv = lib.get('tv') or 'TBD'

    details_table = (
        '<div class="kg-card kg-html-card"><h2>Game Details</h2>'
        '<table><tbody>'
        + _row('Matchup', f'{TEAM_NAME} vs. {opponent}')
        + _row('Date', local_date)
        + _row('Tipoff (UTC)', tipoff)
        + _row('Location', location)
        + _row('TV', tv)
        + (_row('Series Context', game_context) if game_context else '')
        + '</tbody></table></div>'
    )

    parts = [PHOTOS_LINK, details_table]

    if lib.get('matchup_matrix_src'):
        parts.append(
            f'<figure class="kg-card kg-image-card kg-width-wide"><img src="{escape(lib["matchup_matrix_src"])}" class="kg-image" alt="Matchup matrix" loading="lazy"></figure>'
        )

    okc_inj = lib.get('okc_injuries') or []
    opp_inj = lib.get('opp_injuries') or []
    inj_meaningful = any(x.strip().upper() != 'TBD' for x in okc_inj + opp_inj if isinstance(x, str))
    if inj_meaningful:
        parts.extend([
            '<h2>Injury Report</h2>',
            _two_col_table('Thunder', okc_inj or ['TBD'], opponent, opp_inj or ['TBD']),
        ])

    parts.extend([
        '<h2>Likely Starters</h2>',
        _two_col_table('Thunder', lib.get('okc_likely_starters') or ['TBD'], opponent, lib.get('opp_likely_starters') or ['TBD']),
    ])
    return '\n'.join(p for p in parts if p)


def build_scoreboard_html(game: Dict, series_or_record_line: str) -> str:
    return '\n'.join(
        p for p in [
            f'<p style="text-align:center;"><strong>{escape(safe_str(series_or_record_line))}</strong></p>',
            _official_links(game),
        ] if p
    )


def build_dayafter_html(game: Dict, scoreboard_image_url: str, scoreboard_caption: str) -> str:
    parts = [
        PHOTOS_LINK,
        f'<figure class="kg-card kg-image-card kg-card-hascaption"><img src="{escape(scoreboard_image_url)}" class="kg-image" alt="Final score graphic" loading="lazy"><figcaption>{escape(scoreboard_caption)}</figcaption></figure>',
        '<h2>Postgame Bolts</h2>',
        '<p>[EDITOR]</p>',
        '<h2>One Key Takeaway</h2>',
        '<p>[EDITOR]</p>',
        '<p>[INSERT FREE PREVIEW BREAK HERE]</p>',
        _official_links(game),
    ]
    return '\n'.join(p for p in parts if p)


def build_podcast_html(title: str, summary: str, link: str) -> str:
    return '\n'.join([
        f'<h2>{escape(title)}</h2>',
        f'<p>{escape(summary or "")}</p>',
        f'<p><a href="{escape(link)}">Listen</a></p>',
        '<p><a href="https://podcasts.apple.com/us/podcast/the-daily-thunder-podcast/id1492195735">Apple</a> | '
        '<a href="https://youtube.com/playlist?list=PLLuLxky7tVJzxCyQImdWgzQThTWPitqi2&si=2fg3XVrKBtw7VnKP">YouTube</a> | '
        '<a href="https://www.dailythunder.com/tag/thunder-podcast/">All episodes</a></p>',
    ])
