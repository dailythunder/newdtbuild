from html import escape
from typing import Dict, List

from .utils import safe_str

TEAM_NAME = 'Oklahoma City Thunder'
PHOTOS_LINK = '<p style="text-align:center;"><a href="https://www.nba.com/thunder/photos">PHOTOS⚡THUNDER</a></p>'


def _row(label: str, value: str) -> str:
    return f'<tr><td><strong>{escape(label)}</strong></td><td>{escape(safe_str(value) or "TBD")}</td></tr>'


def _two_col_table(title_left: str, items_left: List[str], title_right: str, items_right: List[str]) -> str:
    left_lines = '<br>'.join(escape(i) for i in (items_left or ['TBD']))
    right_lines = '<br>'.join(escape(i) for i in (items_right or ['TBD']))
    return (
        '<!--kg-card-begin: html-->'
        '<table class="matchup-table">'
        '<thead><tr>'
        f'<th>{escape(title_left)}</th>'
        f'<th>{escape(title_right)}</th>'
        '</tr></thead>'
        '<tbody><tr>'
        f'<td>{left_lines}</td>'
        f'<td>{right_lines}</td>'
        '</tr></tbody>'
        '</table>'
        '<!--kg-card-end: html-->'
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


def _dayafter_top_links(game: Dict) -> str:
    links = game.get('links', {})
    out = ['<a href="https://www.nba.com/thunder/photos">PHOTOS⚡THUNDER</a>']
    if links.get('nba_pbp'):
        out.append(f'<a href="{escape(links["nba_pbp"])}">NBA Play-by-Play</a>')
    if links.get('courtsketch'):
        out.append(f'<a href="{escape(links["courtsketch"])}">CourtSketch Box Score</a>')
    return '<p style="text-align:center;">' + ' | '.join(out) + '</p>'


def build_pregame_html(game: Dict, season_config: Dict) -> str:
    lib = game.get('library', {})
    render = game.get('render_context', {})
    opponent = game.get('opponent') or 'Opponent'

    details = [
        f"<li><strong>Date:</strong> {escape(safe_str(render.get('date_display') or 'TBD'))}</li>",
        f"<li><strong>Tip Time:</strong> {escape(safe_str(render.get('tip_display') or 'TBD'))}</li>",
        f"<li><strong>Location:</strong> {escape(safe_str(lib.get('location') or 'TBD'))}</li>",
        f"<li><strong>TV:</strong> {escape(safe_str(lib.get('tv') or 'TBD'))}</li>",
        f"<li><strong>Line:</strong> {escape(safe_str(lib.get('line') or 'TBD'))}</li>",
        f"<li><strong>Round 1 Series:</strong> {escape(safe_str(render.get('series_status') or 'TBD'))}</li>",
    ]

    parts = [
        PHOTOS_LINK,
        '<h2>Game Details</h2>',
        '<ul>' + ''.join(details) + '</ul>',
    ]

    okc_inj = [x for x in (lib.get('okc_injuries') or []) if isinstance(x, str) and x.strip()]
    opp_inj = [x for x in (lib.get('opp_injuries') or []) if isinstance(x, str) and x.strip()]
    meaningful = lambda items: any(i.strip().upper() != 'TBD' for i in items)
    if meaningful(okc_inj) or meaningful(opp_inj):
        parts.extend([
            '<h2>Injury Report</h2>',
            _two_col_table('OKC', okc_inj or ['None'], render.get('opp_header') or f'OPP ({opponent[:3].upper()})', opp_inj or ['None']),
        ])

    okc_starters = [x for x in (lib.get('okc_likely_starters') or []) if isinstance(x, str) and x.strip()]
    opp_starters = [x for x in (lib.get('opp_likely_starters') or []) if isinstance(x, str) and x.strip()]
    parts.extend([
        '<h2>Likely Starters</h2>',
        _two_col_table('OKC', okc_starters[:5] or ['TBD'], render.get('opp_header') or f'OPP ({opponent[:3].upper()})', opp_starters[:5] or ['TBD']),
    ])

    if lib.get('matchup_matrix_src'):
        parts.append(
            f'<figure class="kg-card kg-image-card kg-width-wide"><img src="{escape(lib["matchup_matrix_src"])}" class="kg-image" alt="Matchup matrix" loading="lazy"></figure>'
        )

    return '\n'.join(p for p in parts if p)


def build_scoreboard_html(game: Dict, series_or_record_line: str) -> str:
    return '\n'.join(
        p for p in [
            (
                f'<h2>Final: Thunder def. {escape(safe_str(game.get("opponent") or "Opponent"))}, '
                f'{escape(safe_str(game.get("thunder_score") or "TBD"))}-{escape(safe_str(game.get("opponent_score") or "TBD"))}</h2>'
                if game.get('result') == 'W'
                else f'<h2>Final: {escape(safe_str(game.get("opponent") or "Opponent"))} def. Thunder, '
                     f'{escape(safe_str(game.get("opponent_score") or "TBD"))}-{escape(safe_str(game.get("thunder_score") or "TBD"))}</h2>'
            ),
            f'<p style="text-align:center;"><strong>{escape(safe_str(series_or_record_line))}</strong></p>',
            _official_links(game),
            '<p><strong>Stay tuned to Daily Thunder for full postgame coverage.</strong></p>',
        ] if p
    )


def build_dayafter_html(game: Dict, scoreboard_image_url: str, scoreboard_caption: str) -> str:
    parts = [
        _dayafter_top_links(game),
        f'<figure class="kg-card kg-image-card kg-card-hascaption"><img src="{escape(scoreboard_image_url)}" class="kg-image" alt="Final score graphic" loading="lazy"><figcaption>{escape(scoreboard_caption)}</figcaption></figure>',
        '<h2>Postgame Bolts</h2>',
        '<p>[EDITOR]</p>',
        '<h2>One Key Takeaway</h2>',
        '<p>[EDITOR]</p>',
        '<p>[INSERT FREE PREVIEW BREAK HERE]</p>',
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
