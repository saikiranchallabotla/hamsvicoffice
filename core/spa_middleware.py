"""
SPA Middleware - Extracts partial content for SPA (Single Page Application) requests.

When a request includes the X-SPA-Request header, this middleware intercepts the
rendered HTML response and extracts just the content portion, returning it as JSON.
This allows the client-side SPA router to swap content without full page reloads.

Supports two layout types:
- 'app': Pages extending base_modern.html (sidebar + header + content area)
- 'auth': Pages extending auth_base.html (centered auth card layout)
- 'standalone': Full HTML pages that don't use the standard base templates
"""

import json
import re
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


# Markers inserted into base templates to delimit extractable content
MARKERS = {
    'app': {
        'content': ('<!-- SPA:APP:CONTENT_START -->', '<!-- SPA:APP:CONTENT_END -->'),
        'title': ('<!-- SPA:APP:TITLE_START -->', '<!-- SPA:APP:TITLE_END -->'),
        'styles': ('/* SPA:APP:STYLES_START */', '/* SPA:APP:STYLES_END */'),
        'scripts': ('<!-- SPA:APP:SCRIPTS_START -->', '<!-- SPA:APP:SCRIPTS_END -->'),
        'head': ('<!-- SPA:APP:HEAD_START -->', '<!-- SPA:APP:HEAD_END -->'),
    },
    'auth': {
        'content': ('<!-- SPA:AUTH:CONTENT_START -->', '<!-- SPA:AUTH:CONTENT_END -->'),
        'styles': ('/* SPA:AUTH:STYLES_START */', '/* SPA:AUTH:STYLES_END */'),
        'scripts': ('<!-- SPA:AUTH:SCRIPTS_START -->', '<!-- SPA:AUTH:SCRIPTS_END -->'),
    },
    'classic': {
        'content': ('<!-- SPA:CLASSIC:CONTENT_START -->', '<!-- SPA:CLASSIC:CONTENT_END -->'),
        'styles': ('/* SPA:CLASSIC:STYLES_START */', '/* SPA:CLASSIC:STYLES_END */'),
        'scripts': ('<!-- SPA:CLASSIC:SCRIPTS_START -->', '<!-- SPA:CLASSIC:SCRIPTS_END -->'),
        'head': ('<!-- SPA:CLASSIC:HEAD_START -->', '<!-- SPA:CLASSIC:HEAD_END -->'),
    },
}

# URLs that should never be SPA-intercepted (file downloads, API endpoints, etc.)
BYPASS_PREFIXES = (
    '/admin/',
    '/admin-panel/',
    '/health/',
    '/api/',
    '/static/',
    '/media/',
)

# Content types that indicate non-HTML responses (downloads, API, etc.)
NON_HTML_TYPES = (
    'application/json',
    'application/octet-stream',
    'application/pdf',
    'application/vnd',
    'application/zip',
    'text/csv',
    'text/plain',
)


def _extract_between(html, start_marker, end_marker):
    """Extract content between two markers, or return None if not found."""
    start_idx = html.find(start_marker)
    if start_idx == -1:
        return None
    start_idx += len(start_marker)
    end_idx = html.find(end_marker, start_idx)
    if end_idx == -1:
        return None
    return html[start_idx:end_idx].strip()


def _extract_title_from_html(html):
    """Extract <title> content from full HTML."""
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ''


def _extract_body_content(html):
    """Extract content inside <body> tags for standalone pages."""
    match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else html


def _extract_head_extras(html):
    """Extract <style> and <link> tags from <head> for standalone pages."""
    head_match = re.search(r'<head[^>]*>(.*?)</head>', html, re.DOTALL | re.IGNORECASE)
    if not head_match:
        return ''
    head = head_match.group(1)
    # Extract style tags and non-standard link tags (skip bootstrap, fonts, etc.)
    styles = re.findall(r'<style[^>]*>.*?</style>', head, re.DOTALL | re.IGNORECASE)
    return '\n'.join(styles)


class SPAMiddleware(MiddlewareMixin):
    """
    Middleware that intercepts responses for SPA requests and returns
    partial content as JSON instead of full HTML pages.
    """

    def process_request(self, request):
        """Mark SPA requests for processing in process_response."""
        request._is_spa_request = request.META.get('HTTP_X_SPA_REQUEST') == 'true'

    def process_response(self, request, response):
        """Extract and return partial content for SPA requests."""
        # Skip if not an SPA request
        if not getattr(request, '_is_spa_request', False):
            return response

        # Skip bypass paths
        path = request.path
        if any(path.startswith(prefix) for prefix in BYPASS_PREFIXES):
            return response

        # Handle redirects - return redirect URL for the SPA router to follow
        if response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.get('Location', '/')
            resp = JsonResponse({
                'type': 'redirect',
                'url': redirect_url,
            })
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp['Vary'] = 'X-SPA-Request'
            return resp

        # Skip non-HTML responses (file downloads, JSON APIs, etc.)
        content_type = response.get('Content-Type', '')
        if any(ct in content_type for ct in NON_HTML_TYPES):
            # Tell the SPA router to do a normal navigation for this URL
            resp = JsonResponse({
                'type': 'download',
                'url': path,
            })
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp['Vary'] = 'X-SPA-Request'
            return resp

        # Skip non-200 responses
        if response.status_code != 200:
            return response

        # Get the HTML content
        try:
            html = response.content.decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            return response

        # Try to extract content using markers

        # Check for app layout (base_modern.html)
        app_content = _extract_between(html, *MARKERS['app']['content'])
        if app_content is not None:
            page_title = _extract_between(html, *MARKERS['app']['title']) or ''
            styles = _extract_between(html, *MARKERS['app']['styles']) or ''
            scripts = _extract_between(html, *MARKERS['app']['scripts']) or ''
            head = _extract_between(html, *MARKERS['app']['head']) or ''

            resp = JsonResponse({
                'type': 'content',
                'layout': 'app',
                'content': app_content,
                'pageTitle': page_title,
                'styles': styles,
                'scripts': scripts,
                'head': head,
                'title': _extract_title_from_html(html),
            })
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp['Vary'] = 'X-SPA-Request'
            return resp

        # Check for auth layout (auth_base.html)
        auth_content = _extract_between(html, *MARKERS['auth']['content'])
        if auth_content is not None:
            styles = _extract_between(html, *MARKERS['auth']['styles']) or ''
            scripts = _extract_between(html, *MARKERS['auth']['scripts']) or ''

            resp = JsonResponse({
                'type': 'content',
                'layout': 'auth',
                'content': auth_content,
                'styles': styles,
                'scripts': scripts,
                'title': _extract_title_from_html(html),
            })
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp['Vary'] = 'X-SPA-Request'
            return resp

        # Check for classic layout (core/base.html, base.html)
        classic_content = _extract_between(html, *MARKERS['classic']['content'])
        if classic_content is not None:
            styles = _extract_between(html, *MARKERS['classic']['styles']) or ''
            scripts = _extract_between(html, *MARKERS['classic']['scripts']) or ''
            head = _extract_between(html, *MARKERS['classic']['head']) or ''

            resp = JsonResponse({
                'type': 'content',
                'layout': 'classic',
                'content': classic_content,
                'styles': styles,
                'scripts': scripts,
                'head': head,
                'title': _extract_title_from_html(html),
            })
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp['Vary'] = 'X-SPA-Request'
            return resp

        # Standalone page - extract body content
        body = _extract_body_content(html)
        head_styles = _extract_head_extras(html)

        resp = JsonResponse({
            'type': 'content',
            'layout': 'standalone',
            'content': body,
            'styles': head_styles,
            'title': _extract_title_from_html(html),
        })
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp['Vary'] = 'X-SPA-Request'
        return resp
