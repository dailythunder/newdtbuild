from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_scoreboard_html
from dtlib.nba_sources import compute_live_window
from dtlib.state_io import load_all, save_all
from dtlib.utils import slugify, utcnow_iso


def main() -> None:
    data = load_all()
    previous = compute_live_window(data['season_state'].get('games', []))['previous_game']
    if not previous or previous.get('status') != 'final':
        print('No final game for scoreboard.')
        return
    if previous['automation'].get('scoreboard_complete'):
        print('Scoreboard already completed.')
        return

    title = f"Thunder Scoreboard: {previous.get('opponent') or 'Opponent'}"
    slug = previous['automation'].get('scoreboard_slug') or slugify(f"scoreboard {previous.get('game_id')}")
    post = GhostClient().upsert_draft(
        title=title,
        slug=slug,
        html=build_scoreboard_html(previous, data['series_config']),
        tags=['Thunder', 'Scoreboard'],
        feature_image=previous.get('assets', {}).get('scoreboard_image') or previous.get('library', {}).get('feature_image_src'),
        custom_excerpt='Thunder Scoreboard',
        update_if_unpublished=False,
    )
    previous['automation']['scoreboard_slug'] = slug
    previous['automation']['scoreboard_complete'] = True
    data['content_state']['ghost_posts'][slug] = {'id': post.get('id'), 'lane': 'scoreboard', 'updated_utc': utcnow_iso()}
    save_all(data)
    print(f'Scoreboard created: {slug}')


if __name__ == '__main__':
    main()
