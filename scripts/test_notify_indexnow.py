#!/usr/bin/env python3
"""Regression checks for canonical URL mapping in the IndexNow notifier."""

from notify_indexnow import public_url, listed_urls


cases = {
    "index.html": "https://a-samadi.com/",
    "fa/index.html": "https://a-samadi.com/fa/",
    "ar/index.html": "https://a-samadi.com/ar/",
    "fa/writing/index.html": "https://a-samadi.com/fa/writing/",
    "ar/writing/index.html": "https://a-samadi.com/ar/writing/",
    "fa/writing/passkeys-face-id.html": "https://a-samadi.com/fa/writing/passkeys-face-id.html",
}
canonical = listed_urls()
for path, expected in cases.items():
    assert public_url(path) == expected, path
    assert expected in canonical, expected
print("IndexNow canonical URL mapping verified")
