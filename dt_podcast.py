import feedparser

from dtlib.ghost_client import GhostClient
from dtlib.html_templates import build_podcast_html
from dtlib.state_io import load_all, save_all
from dtlib.utils import slugify, utcnow_iso

RSS_URL = 'https://anchor.fm/s/11ffdfa0/podcast/rss'
PODCAST_FEATURE_IMAGE = 'https://storage.ghost.io/c/f2/f9/f2f98597-fc28-4a31-8135-86802fa12f06/content/images/2024/11/1000001721.png'


def _podcast_title(raw_title: str) -> str:
    title = (raw_title or 'The Daily Thunder Podcast').strip()
    if title.lower().startswith('podcast:'):
        return title
    return f'Podcast: {title}'


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
    raw_title = getattr(entry, 'title', 'The Daily Thunder Podcast')
    title = _podcast_title(raw_title)
    summary = getattr(entry, 'summary', '')
    link = getattr(entry, 'link', '') or getattr(entry, 'id', '') or RSS_URL
    slug = slugify(title)
    ghost = GhostClient()

    existing = ghost.find_post_by_slug(slug) if ghost.enabled else None
    if existing and existing.get('status') == 'published':
        print(f'Podcast already published for slug={slug}; skipping.')
        return

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
        tags=['Thunder Podcast', 'Podcast', 'oklahoma city podcast'],
        feature_image=PODCAST_FEATURE_IMAGE,
        custom_excerpt='The Daily Thunder Podcast',
        visibility='public',
        featured=False,
        update_if_unpublished=True,
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
