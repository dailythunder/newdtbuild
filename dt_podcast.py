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
    if getattr(feed, 'bozo', False):
        print(f"Podcast feed parse warning: {getattr(feed, 'bozo_exception', 'unknown parse failure')}")
        return
    status = getattr(feed, 'status', None)
    if status and int(status) >= 400:
        print(f'Podcast feed HTTP status: {status}')
        return
    if not feed.entries:
        print('No podcast entries found.')
        return

    entry = feed.entries[0]
    key = getattr(entry, 'id', None) or getattr(entry, 'link', None) or getattr(entry, 'title', None)
    if not key or key in seen:
        print('No new podcast episode.')
        return

    title = getattr(entry, 'title', 'The Daily Thunder Podcast')
    summary = getattr(entry, 'summary', '')
    link = getattr(entry, 'link', RSS_URL)
    slug = slugify(f'podcast {title}')
    post = GhostClient().upsert_draft(
        title=title,
        slug=slug,
        html=build_podcast_html(title, summary, link),
        tags=['Thunder Podcast'],
        custom_excerpt='The Daily Thunder Podcast',
        update_if_unpublished=False,
    )
    data['content_state']['podcast_seen_keys'].append(key)
    data['content_state']['ghost_posts'][slug] = {'id': post.get('id'), 'lane': 'podcast', 'updated_utc': utcnow_iso()}
    save_all(data)
    print(f'Podcast draft created: {slug}')


if __name__ == '__main__':
    main()
