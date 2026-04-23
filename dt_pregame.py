from typing import Optional

from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_pregame_html
from dtlib.state_io import load_all, save_all
from dtlib.utils import parse_iso, slugify, utcnow, utcnow_iso

WINDOWS = {6, 5, 4, 3, 2, 1}


def eligible_game(games) -> Optional[dict]:
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
    game = eligible_game(data['season_state'].get('games', []))
    if not game:
        print('No eligible pregame window.')
        return

    opponent = game.get('opponent') or 'Opponent'
    title = f"Thunder Pregame Primer: {opponent}"
    slug = game['automation'].get('pregame_slug') or slugify(f"pregame {game.get('game_id') or game.get('local_date')} {opponent}")
    html = build_pregame_html(game, data['season_config'])
    ghost = GhostClient()
    post = ghost.upsert_draft(
        title=title,
        slug=slug,
        html=html,
        tags=['Thunder', 'Pregame'],
        feature_image=game.get('library', {}).get('feature_image_src') or game.get('assets', {}).get('game_image'),
        custom_excerpt=f"Pregame primer for Thunder vs. {opponent}",
        update_if_unpublished=True,
    )
    game['automation']['pregame_slug'] = slug
    data['content_state']['ghost_posts'][slug] = {'id': post.get('id'), 'lane': 'pregame', 'updated_utc': utcnow_iso()}
    save_all(data)
    print(f'Pregame upserted: {slug}')


if __name__ == '__main__':
    main()
