# products/views.py

import hashlib
import hmac
import time
import json

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache

from .models import SubSubCategory


# ─── SECRET: put this in settings.py as CATEGORY_API_SECRET ───────────────────
# from django.conf import settings
# CATEGORY_API_SECRET = getattr(settings, "CATEGORY_API_SECRET", "change-me-in-prod")
# ──────────────────────────────────────────────────────────────────────────────

import os
CATEGORY_API_SECRET = os.environ.get("CATEGORY_API_SECRET", "av-secret-2026-xK9")


def _make_hmac_token(user_id: int, window: int) -> str:
    """
    Generate a short-lived HMAC token tied to (user_id + 5-minute time window).
    The client must send this token back with every search request.
    Window = current unix-time // 300  (rotates every 5 min).
    """
    message = f"{user_id}:{window}".encode()
    secret  = CATEGORY_API_SECRET.encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:32]


def _current_window() -> int:
    """Return current 5-minute window index."""
    return int(time.time()) // 300


def _valid_token(user_id: int, token: str) -> bool:
    """Accept current window and the immediately preceding one (clock skew)."""
    w = _current_window()
    return (
        hmac.compare_digest(token, _make_hmac_token(user_id, w))
        or hmac.compare_digest(token, _make_hmac_token(user_id, w - 1))
    )


def _rate_limit(user_id: int, limit: int = 30, period: int = 60) -> bool:
    """
    Simple Redis/cache-based rate limiter.
    Returns True if the request is ALLOWED, False if limit exceeded.
    """
    key   = f"cat_rl:{user_id}"
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, timeout=period)
    return True


def _shuffle_keys(obj: dict) -> dict:
    """
    Rename result keys so they differ each request — makes automated
    scraping / schema-mapping much harder.
    The JS client knows to read these renamed keys.
    """
    aliases = {
        "id":   "k",
        "name": "v",
        "path": "p",
    }
    return {aliases.get(k, k): v for k, v in obj.items()}


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC: issue a fresh token (called once on page load)
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def category_token(request):
    """
    Called on page load (GET) to receive a short-lived search token.
    Token rotates every 5 minutes.
    """
    token = _make_hmac_token(request.user.pk, _current_window())
    # TTL tells the JS how long until it should refresh the token (max 5 min)
    ttl   = 300 - (int(time.time()) % 300)
    return JsonResponse({"t": token, "ttl": ttl})


# ──────────────────────────────────────────────────────────────────────────────
# PROTECTED: search categories
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@require_GET
def search_categories(request):

    # 1. Rate limit
    if not _rate_limit(request.user.pk):
        return JsonResponse({"e": "too_many_requests"}, status=429)

    # 2. Token validation
    token = request.GET.get("_t", "")
    if not token or not _valid_token(request.user.pk, token):
        return JsonResponse({"e": "invalid_token"}, status=403)

    # 3. Query
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"r": []})

    # Limit query length to avoid regex bombs
    query = query[:60]

    categories = (
        SubSubCategory.objects
        .select_related(
            "sub_category__category__super_category"
        )
        .filter(name__icontains=query)[:10]          # max 10 results
    )

    data = []
    for cat in categories:
        raw = {
            "id":   cat.id,
            "name": cat.name,
            "path": (
                f"{cat.sub_category.category.super_category.name} › "
                f"{cat.sub_category.category.name} › "
                f"{cat.sub_category.name} › "
                f"{cat.name}"
            ),
        }
        data.append(_shuffle_keys(raw))

    # 4. Return with shuffled keys + no caching headers
    response = JsonResponse({"r": data})
    response["Cache-Control"]  = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"]         = "no-cache"
    response["X-Content-Type"] = "nosniff"
    return response