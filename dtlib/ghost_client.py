import os
import time
from typing import Any, Dict, List, Optional

import jwt
import requests

from .utils import is_abs_http_url


class GhostClient:
    def __init__(self) -> None:
        self.base_url = os.getenv('GHOST_URL', '').rstrip('/')
        self.admin_key = os.getenv('GHOST_ADMIN_KEY', '')

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.admin_key)

    def is_real_post(self, post: Optional[Dict[str, Any]]) -> bool:
        return bool(post and post.get('id') and post.get('id') != 'dry-run')

    def _token(self) -> str:
        key_id, secret = self.admin_key.split(':')
        iat = int(time.time())
        payload = {'iat': iat, 'exp': iat + 5 * 60, 'aud': '/admin/'}
        return jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})

    def _headers(self) -> Dict[str, str]:
        return {'Authorization': f'Ghost {self._token()}'}

    def find_post_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or not slug:
            return None
        url = f'{self.base_url}/ghost/api/admin/posts/slug/{slug}/'
        r = requests.get(url, headers=self._headers(), timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        posts = r.json().get('posts', [])
        return posts[0] if posts else None

    def _sanitize_html(self, html: Optional[str]) -> str:
        text = html or ''
        return text.replace('\x00', '').replace('None', '')

    def upsert_draft(
        self,
        title: str,
        slug: str,
        html: str,
        tags: Optional[List[str]] = None,
        feature_image: Optional[str] = None,
        custom_excerpt: Optional[str] = None,
        visibility: Optional[str] = None,
        featured: Optional[bool] = None,
        update_if_unpublished: bool = True,
    ) -> Dict[str, Any]:
        if not self.enabled:
            print(f'Ghost disabled; dry-run for slug={slug}')
            return {'id': 'dry-run', 'slug': slug, 'status': 'draft'}

        html = self._sanitize_html(html)
        existing = self.find_post_by_slug(slug)
        if existing and existing.get('status') == 'published':
            return existing
        if existing and not update_if_unpublished:
            return existing

        base_post: Dict[str, Any] = {'title': title, 'slug': slug, 'html': html, 'status': 'draft'}
        if tags:
            clean_tags = [t for t in tags if isinstance(t, str) and t.strip()]
            if clean_tags:
                base_post['tags'] = clean_tags
        if custom_excerpt and isinstance(custom_excerpt, str) and custom_excerpt.strip():
            base_post['custom_excerpt'] = custom_excerpt.strip()
        if is_abs_http_url(feature_image):
            base_post['feature_image'] = feature_image
        if visibility in {'public', 'members', 'paid'}:
            base_post['visibility'] = visibility
        if isinstance(featured, bool):
            base_post['featured'] = featured

        if existing:
            base_post['id'] = existing['id']
            base_post['updated_at'] = existing['updated_at']
            url = f"{self.base_url}/ghost/api/admin/posts/{existing['id']}/?source=html"
            method = requests.put
        else:
            url = f'{self.base_url}/ghost/api/admin/posts/?source=html'
            method = requests.post

        for attempt, reduced in ((1, False), (2, True)):
            post = dict(base_post)
            if reduced:
                post = {'title': title, 'slug': slug, 'html': html, 'status': 'draft'}
            response = method(url, json={'posts': [post]}, headers=self._headers(), timeout=30)
            if response.ok:
                return response.json()['posts'][0]
            print(f'Ghost {response.status_code} attempt={attempt} slug={slug}: {response.text}')
            if response.status_code != 400:
                response.raise_for_status()

        raise requests.HTTPError(f'Ghost rejected payload for slug={slug}', response=response)
