from __future__ import annotations

import unittest

from app.services.cache import AsyncTTLCache


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_hit_and_stale_fallback(self) -> None:
        cache = AsyncTTLCache()
        calls = 0

        async def first_loader():
            nonlocal calls
            calls += 1
            return {"value": 1}

        first = await cache.get_or_load("key", 30, 60, first_loader)
        second = await cache.get_or_load("key", 30, 60, first_loader)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(calls, 1)

        async def failing_loader():
            raise RuntimeError("source down")

        stale = await cache.get_or_load(
            "key",
            30,
            60,
            failing_loader,
            force=True,
        )
        self.assertTrue(stale.cache_hit)
        self.assertTrue(stale.stale)
        self.assertIn("source down", stale.error or "")


if __name__ == "__main__":
    unittest.main()
