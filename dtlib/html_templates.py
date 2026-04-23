from html import escape
from typing import Dict, List, Optional

from .utils import safe_str

TEAM_NAME = 'Oklahoma City Thunder'

NEWSLETTER_CTA = '''<div class="kg-card kg-cta-card kg-cta-bg-yellow kg-cta-immersive kg-cta-has-img kg-cta-link-accent kg-cta-centered" data-layout="immersive">
  <div class="kg-cta-content">
    <div class="kg-cta-content-inner">
      <div class="kg-cta-text">
        <p><strong>Thanks for subscribing to The Daily Thunder Newsletter!</strong> Manage your notifications at <a href="https://www.dailythunder.com/#/portal/">DailyThunder.com</a> to receive every post in your inbox in addition to our featured articles.</p>
      </div>
      <a href="https://www.dailythunder.com/#/portal/" class="kg-cta-button kg-style-accent" style="color:#FFFFFF;">Update My Preferences</a>
    </div>
  </div>
</div>'''


def _image_block(src: Optional[str], srcset: Optional[str] = None) -> str:
    if not src:
        return ''
    attrs = f'src="{escape(src)}" class="kg-image" alt="" loading="lazy"'
    if srcset:
        attrs += f' srcset="{escape(srcset)}" sizes="(min-width: 1200px) 1200px"'
    return f'<figure class="kg-card kg-image-card kg-width-wide"><img {attrs}></figure>'


def _two_col(title_left: str, items_left: List[str], title_right: str, items_right: List[str]) -> str:
    def render(title, items):
        lis = ''.join(f'<li>{escape(i)}</li>' for i in items) or '<li>TBD</li>'
        return f'<div><h3>{escape(title)}</h3><ul>{lis}</ul></div>'
    return f'<div class="kg-card kg-html-card"><div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;">{render(title_left, items_left)}{render(title_right, items_right)}</div></div>'


def _official_links(game: Dict) -> str:
    links = game.get('links', {})
    out = []
    if links.get('nba_pbp'):
        out.append(f'<a href="{escape(links["nba_pbp"])}">NBA Play-by-Play</a>')
    if links.get('courtsketch'):
        out.append(f'<a href="{escape(links["courtsketch"])}">CourtSketch</a>')
    if not out:
        return ''
    return '<p>' + ' | '.join(out) + '</p>'


def build_pregame_html(game: Dict, season_config: Dict) -> str:
    lib = game.get('library', {})
    parts = [
        _image_block(lib.get('feature_image_src') or game.get('assets', {}).get('game_image'), lib.get('feature_image_srcset')),
        '<p style="text-align:center;"><a href="https://www.nba.com/thunder/photos">PHOTOS⚡THUNDER</a></p>',
        '<h2>Game Details</h2>',
        f'<p><strong>{escape(TEAM_NAME)}</strong> vs. <strong>{escape(safe_str(game.get("opponent_full_name") or game.get("opponent") or "Opponent"))}</strong></p>',
        f'<p>{escape(safe_str(game.get("local_date") or "TBD"))}</p>',
        f'<p>{escape(safe_str(lib.get("location") or ""))}</p>' if lib.get('location') else '',
        f'<p>{escape(safe_str(lib.get("tv") or ""))}</p>' if lib.get('tv') else '',
        _official_links(game),
        _image_block(lib.get('matchup_matrix_src'), lib.get('matchup_matrix_srcset')),
        '<h2>Injury Report</h2>',
        _two_col('Thunder', lib.get('okc_injuries') or ['TBD'], game.get('opponent') or 'Opponent', lib.get('opp_injuries') or ['TBD']),
        '<h2>Likely Starters</h2>',
        _two_col('Thunder', lib.get('okc_likely_starters') or ['TBD'], game.get('opponent') or 'Opponent', lib.get('opp_likely_starters') or ['TBD']),
        NEWSLETTER_CTA,
    ]
    return '\n'.join(p for p in parts if p)


def build_scoreboard_html(game: Dict, series_config: Dict) -> str:
    result = f"{game.get('thunder_score', '')}-{game.get('opponent_score', '')}"
    series_line = series_config.get('series_label') if game.get('season_phase') == 'playoffs' else 'Regular Season'
    parts = [
        f'<p style="text-align:center;"><strong>{escape(safe_str(series_line))}</strong></p>',
        f'<h2>Final Score</h2><p>{escape(TEAM_NAME)} {escape(safe_str(game.get("thunder_score")))} - {escape(safe_str(game.get("opponent_score")))} {escape(safe_str(game.get("opponent") or "Opponent"))}</p>',
        _official_links(game),
        NEWSLETTER_CTA,
    ]
    return '\n'.join(p for p in parts if p)


def build_dayafter_html(game: Dict, series_config: Dict) -> str:
    lib = game.get('library', {})
    series_line = series_config.get('series_label') if game.get('season_phase') == 'playoffs' else 'Regular Season'
    parts = [
        f'<p style="text-align:center;"><strong>{escape(safe_str(series_line))}</strong></p>',
        _image_block(lib.get('feature_image_src') or game.get('assets', {}).get('game_image'), lib.get('feature_image_srcset')),
        '<p style="text-align:center;"><a href="https://www.nba.com/thunder/photos">PHOTOS⚡THUNDER</a></p>',
        '<h2>Postgame Bolts</h2>',
        '<p>[EDITOR]</p>',
        '<h2>One Key Takeaway</h2>',
        '<p>[EDITOR]</p>',
        '<p>[INSERT FREE PREVIEW BREAK HERE]</p>',
        _official_links(game),
        NEWSLETTER_CTA,
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
