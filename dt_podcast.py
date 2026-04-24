import feedparser

from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_podcast_html
from dtlib.state_io import load_all, save_all
from dtlib.utils import slugify, utcnow_iso

RSS_URL = 'https://anchor.fm/s/11ffdfa0/podcast/rss'


def main() -> None:
    data = load_all()
    seen = set(data['content_state'].get('podcast_seen_keys', []))

    try:
        feed = feedparser.parse(RSS_URL)
    except Exception as exc:
        print(f'Podcast feed failed: {exc}')
        return
    if not feed.entries:
        print('No podcast entries found.')
        return

    entry = feed.entries[0]
    key = getattr(entry, 'id', None) or getattr(entry, 'link', None) or getattr(entry, 'title', None)
    title = getattr(entry, 'title', 'The Daily Thunder Podcast')
    summary = getattr(entry, 'summary', '')
    link = getattr(entry, 'link', RSS_URL)
    slug = slugify(f'podcast {title}')
    ghost = GhostClient()

    if key in seen:
        if ghost.enabled and ghost.find_post_by_slug(slug):
            print('No new podcast episode.')
            return
        print('Resetting stale podcast seen state.')
        data['content_state']['podcast_seen_keys'] = [k for k in data['content_state'].get('podcast_seen_keys', []) if k != key]
        seen.discard(key)

    post = ghost.upsert_draft(
        title=title,
        slug=slug,
        html=build_podcast_html(title, summary, link),
        tags=['Thunder Podcast'],
        custom_excerpt='The Daily Thunder Podcast',
        visibility='public',
        featured=False,
        update_if_unpublished=False,
    )

    if not ghost.is_real_post(post):
        print('Podcast dry-run only; not mutating seen state.')
        save_all(data)
        return

    data['content_state'].setdefault('podcast_seen_keys', []).append(key)
    data['content_state'].setdefault('ghost_posts', {})[slug] = {'id': post.get('id'), 'lane': 'podcast', 'updated_utc': utcnow_iso()}
    save_all(data)
    print(f'Podcast draft created: {slug}')


if __name__ == '__main__':
    main()
