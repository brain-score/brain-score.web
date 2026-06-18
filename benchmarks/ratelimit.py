"""Per-user upload rate limiting for ``benchmarks.views.user.Upload``.

Caps how many model-submission zips a single authenticated user can push to
Jenkins within a rolling window. Without this, a user with valid credentials
could fan out 20 distinct-identifier zips in a few seconds and each would
trigger a full gated-scoring run (each one ~$20-50 of Batch compute and
multi-hour wall time).

Implementation notes
--------------------
Counter is kept in Django's configured cache (``django.core.cache``) — see
``web.settings.get_cache_config()``. One key per user per window. Window TTL
is the rate-limit period itself, so the limit naturally rolls forward as old
counts expire.

Limit choice (5 uploads / 24h): gentle enough that legitimate iteration
doesn't hit it; aggressive enough that obvious flooding gets caught fast.
The weekly limit considered earlier was dropped because the chosen cache
backend (LocMemCache in some environments) does not reliably persist a
key for 7 days across web-server restarts. If a longer-window limit is
later needed, the right answer is a small DB-backed `WebUpload` table, not
a longer cache TTL — see the discussion in the PR that introduced this
module.

Failure-mode considerations
---------------------------
* Cache backend down → ``check_and_record_upload`` swallows the exception
  and returns ``allowed=True`` with a logged warning. Rate limiting is a
  guard-rail, not a security boundary; we'd rather over-permit than
  reject legitimate submissions because Redis hiccupped.
* Web-server restart with in-memory cache → counters reset. Acceptable;
  this is a soft floor, not an audit trail. If you want hard accounting,
  use a DB-backed implementation instead.
* Superusers bypass the check; everyone else is rate-limited identically.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger(__name__)

# (max_count, window_seconds). Add more entries here when a new tier is
# needed; check_and_record_upload iterates whatever is configured.
DAILY_LIMIT = 5
DAILY_WINDOW_SEC = 24 * 60 * 60  # 86400

LIMITS: list[Tuple[str, int, int]] = [
    ("day", DAILY_LIMIT, DAILY_WINDOW_SEC),
]


def _cache_key(user_id: int, window_name: str) -> str:
    return f"web_upload_count:{user_id}:{window_name}"


def get_recent_upload_count(user_id: int, window_name: str = "day") -> int:
    """Return the current upload count for the user in the named window.

    Useful for showing remaining quota on the upload page before the user
    submits. Returns 0 if the cache has no entry (window just rolled over,
    cache miss, or backend unavailable)."""
    try:
        return int(cache.get(_cache_key(user_id, window_name), 0) or 0)
    except Exception:  # noqa: BLE001 — cache failures must not break reads
        logger.warning("rate-limit cache read failed for user=%s window=%s",
                       user_id, window_name, exc_info=True)
        return 0


def check_and_record_upload(user_id: int) -> Tuple[bool, Optional[str]]:
    """Record that ``user_id`` is about to upload; return whether it's allowed.

    Returns
    -------
    (allowed, reason)
        ``allowed=True`` means proceed (and the counter has been incremented).
        ``allowed=False`` means reject; ``reason`` is a human-readable string
        the view layer can show to the submitter.

    Atomicity caveat: we do a get / compare / incr cycle without a lock. A
    user racing two concurrent uploads could squeeze in one extra. Acceptable
    — the limit is a soft cap, not a hard quota. Use a DB-backed
    implementation with row locking if you need strict counting.
    """
    # 1. Check every configured window first. Reject on the first one over.
    for window_name, limit, _window_sec in LIMITS:
        current = get_recent_upload_count(user_id, window_name)
        if current >= limit:
            reason = (
                f"You have reached the limit of {limit} model submissions per "
                f"{window_name}. Please wait and try again later."
            )
            logger.info("rate-limit hit: user=%s window=%s count=%d limit=%d",
                        user_id, window_name, current, limit)
            return False, reason

    # 2. All windows pass — increment each one. ``cache.incr`` requires the
    #    key to exist; on first-of-window, fall through to ``cache.set`` with
    #    the window TTL so the key expires when the window rolls over.
    for window_name, _limit, window_sec in LIMITS:
        key = _cache_key(user_id, window_name)
        try:
            cache.incr(key)
        except ValueError:
            # Key didn't exist → first upload in this window.
            try:
                cache.set(key, 1, window_sec)
            except Exception:  # noqa: BLE001
                logger.warning("rate-limit cache write failed for user=%s window=%s",
                               user_id, window_name, exc_info=True)
        except Exception:  # noqa: BLE001
            logger.warning("rate-limit cache incr failed for user=%s window=%s",
                           user_id, window_name, exc_info=True)

    return True, None
