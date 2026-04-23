from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_dayafter_html
from dtlib.nba_sources import compute_live_window
from dtlib.state_io import load_all, save_all
from dtlib.utils import slugify, utcnow_iso


def main() -> None:
    data = load_all()
    previous = compute_live_window(data['season_state'].get('games', []))['previous_game']
    if not previous or previous.get('status') != 'final':
        print('No final game for day after.')
        return

    ghost = GhostClient()
    ghost_posts = data['content_state'].setdefault('ghost_posts', {})
    existing_slug = previous['automation'].get('dayafter_slug')

    if previous['automation'].get('dayafter_complete'):
        if ghost.enabled and existing_slug and ghost.find_post_by_slug(existing_slug):
            print('Day after already completed.')
            return
        print('Resetting stale day after completion state.')
        previous['automation']['dayafter_complete'] = False
        previous['automation']['dayafter_slug'] = None
        if existing_slug:
            ghost_posts.pop(existing_slug, None)

    opponent = previous.get('opponent') or 'Opponent'
    title = f"Day After Report: Thunder vs. {opponent}"
    slug = previous['automation'].get('dayafter_slug') or slugify(f"day after {previous.get('game_id')} {opponent}")
    post = ghost.upsert_draft(
        title=title,
        slug=slug,
        html=build_dayafter_html(previous, data['series_config']),
        tags=['Thunder', 'Day After'],
        feature_image=previous.get('library', {}).get('feature_image_src') or previous.get('assets', {}).get('game_image'),
        custom_excerpt='Day After Report',
        update_if_unpublished=False,
    )

    if not ghost.is_real_post(post):
        print('Day after dry-run only; not mutating completion state.')
        save_all(data)
        return

    previous['automation']['dayafter_slug'] = slug
    previous['automation']['dayafter_complete'] = True
    ghost_posts[slug] = {'id': post.get('id'), 'lane': 'dayafter', 'updated_utc': utcnow_iso()}
    save_all(data)
    print(f'Day after created: {slug}')


if __name__ == '__main__':
    main()
