"""Tests for the per-user upload rate limiter.

The limiter lives in ``benchmarks.ratelimit`` and is wired into
``benchmarks.views.user.Upload.post`` to cap how many distinct submissions
one user can push in a 24h window. These tests exercise the helper module
directly — view-level integration is harder to cover here (the Upload view
also hits Jenkins via ``requests.post`` and parses a zip) and is best left
to a separate end-to-end test or manual canary.

Cache is reset between tests so counters don't leak across test methods.
"""
from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from benchmarks.ratelimit import (
    DAILY_LIMIT,
    DAILY_WINDOW_SEC,
    check_and_record_upload,
    get_recent_upload_count,
)


# In-memory cache scoped to each test class — keeps counters from leaking
# between tests AND independent of whatever the prod settings configure.
LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ratelimit-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class RateLimitHelperTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_first_upload_is_allowed_and_recorded(self):
        allowed, reason = check_and_record_upload(user_id=1)
        self.assertTrue(allowed)
        self.assertIsNone(reason)
        self.assertEqual(get_recent_upload_count(1), 1)

    def test_exactly_daily_limit_uploads_all_allowed(self):
        for i in range(DAILY_LIMIT):
            allowed, _ = check_and_record_upload(user_id=42)
            self.assertTrue(allowed, f"upload {i + 1}/{DAILY_LIMIT} should be allowed")
        self.assertEqual(get_recent_upload_count(42), DAILY_LIMIT)

    def test_one_over_daily_limit_is_rejected(self):
        for _ in range(DAILY_LIMIT):
            check_and_record_upload(user_id=7)
        allowed, reason = check_and_record_upload(user_id=7)
        self.assertFalse(allowed)
        self.assertIsNotNone(reason)
        self.assertIn(str(DAILY_LIMIT), reason)
        self.assertIn("day", reason)
        # Rejected upload must NOT increment the counter — otherwise a
        # rejected user would keep blowing past the limit and pushing the
        # window expiry further out.
        self.assertEqual(get_recent_upload_count(7), DAILY_LIMIT)

    def test_users_are_isolated_from_each_other(self):
        for _ in range(DAILY_LIMIT):
            check_and_record_upload(user_id=100)
        # user 100 is at the cap
        allowed_100, _ = check_and_record_upload(user_id=100)
        self.assertFalse(allowed_100)
        # user 101 has its own counter, should be allowed
        allowed_101, _ = check_and_record_upload(user_id=101)
        self.assertTrue(allowed_101)
        self.assertEqual(get_recent_upload_count(100), DAILY_LIMIT)
        self.assertEqual(get_recent_upload_count(101), 1)

    def test_get_recent_upload_count_returns_zero_for_new_user(self):
        self.assertEqual(get_recent_upload_count(9999), 0)

    def test_cache_failure_does_not_block_upload(self):
        """Cache backend hiccups must not turn into a 500. The limiter is a
        guard-rail, not a security boundary -- over-permit beats reject."""
        with mock.patch("benchmarks.ratelimit.cache.get", side_effect=RuntimeError("redis down")):
            allowed, reason = check_and_record_upload(user_id=55)
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_window_ttl_matches_daily_window(self):
        """First upload of a window should set the key with the right TTL so
        the counter actually rolls over after 24h. We can't easily
        time-travel in LocMemCache, so check by intercepting cache.set."""
        captured: dict = {}

        def _spy_set(key, value, timeout=None, **_kw):
            captured["key"] = key
            captured["value"] = value
            captured["timeout"] = timeout
            return True

        # cache.incr raises ValueError on a missing key, which triggers the
        # fall-through to cache.set in the helper. That's the path we want
        # to inspect.
        with mock.patch("benchmarks.ratelimit.cache.set", side_effect=_spy_set):
            check_and_record_upload(user_id=200)
        self.assertEqual(captured.get("value"), 1)
        self.assertEqual(captured.get("timeout"), DAILY_WINDOW_SEC)

    def test_concurrent_dictated_by_existing_count_not_size_of_increment(self):
        """The check phase reads `current` then compares against the limit.
        After ``DAILY_LIMIT`` uploads we should reject EVERY subsequent
        attempt -- no off-by-one that lets the (LIMIT+1)th through."""
        for _ in range(DAILY_LIMIT):
            check_and_record_upload(user_id=300)
        for attempt in range(5):
            allowed, _ = check_and_record_upload(user_id=300)
            self.assertFalse(allowed, f"attempt {DAILY_LIMIT + attempt + 1} must be rejected")
