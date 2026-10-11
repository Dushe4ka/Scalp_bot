"""Unit tests for MarketFeedHub refcount symmetry and tick-timeout fallback (no Redis / WS)."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bybit_logic.feeds import hybrid_feed_hub as hub_mod
from bybit_logic.feeds.price_source import PriceSourceMode


class _SilentRedisSubscriber:
    """RedisPriceSubscriber stand-in whose get() never yields a price."""

    def __init__(self, symbol, loop, **_kwargs) -> None:
        self.symbol = symbol
        self.stopped = False

    async def start(self) -> None:
        return None

    async def get(self) -> float:
        await asyncio.Event().wait()
        return 0.0

    def is_stale(self, _stale_sec=None) -> bool:
        return False

    async def stop(self) -> None:
        self.stopped = True


class MarketFeedHubTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.hub = hub_mod.MarketFeedHub()
        self.hub.attach_loop(asyncio.get_running_loop())
        self.acquire = MagicMock(return_value=1)
        self.release = MagicMock(return_value=0)
        self.request_feed = MagicMock()
        self.local_stream = MagicMock()
        patches = [
            patch.object(hub_mod, "acquire_symbol_price_session", self.acquire),
            patch.object(hub_mod, "release_symbol_price_session", self.release),
            patch.object(hub_mod, "request_feed_symbol", self.request_feed),
            patch.object(hub_mod, "RedisPriceSubscriber", _SilentRedisSubscriber),
            patch.object(hub_mod, "PriceStream", MagicMock(return_value=self.local_stream)),
            patch.object(hub_mod, "PRICE_FEED_REDIS_ENABLED", True),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _set_mode(self, mode: PriceSourceMode) -> None:
        self.hub._current_mode = MagicMock(return_value=mode)

    async def test_local_mode_unsubscribe_does_not_touch_refcount(self):
        self._set_mode(PriceSourceMode.LOCAL)
        queue = await self.hub.subscribe("btwusdt")

        await self.hub.unsubscribe("BTWUSDT", queue)

        self.acquire.assert_not_called()
        self.release.assert_not_called()
        self.local_stream.stop.assert_called_once()
        self.assertEqual(self.hub._symbols, {})

    async def test_redis_mode_releases_once_per_session(self):
        self._set_mode(PriceSourceMode.REDIS)
        q1 = await self.hub.subscribe("BTWUSDT")
        q2 = await self.hub.subscribe("BTWUSDT")
        q3 = await self.hub.subscribe("BTWUSDT")
        self.assertEqual(self.acquire.call_count, 3)

        await self.hub.unsubscribe("BTWUSDT", q1)
        await self.hub.unsubscribe("BTWUSDT", q2)
        await self.hub.unsubscribe("BTWUSDT", q3)

        self.assertEqual(self.release.call_count, 3)
        self.assertEqual(self.hub._symbols, {})

    async def test_mixed_modes_release_only_redis_sessions(self):
        self._set_mode(PriceSourceMode.LOCAL)
        q_local = await self.hub.subscribe("BTWUSDT")
        self._set_mode(PriceSourceMode.REDIS)
        q_redis = await self.hub.subscribe("BTWUSDT")

        await self.hub.unsubscribe("BTWUSDT", q_redis)
        await self.hub.unsubscribe("BTWUSDT", q_local)

        self.assertEqual(self.acquire.call_count, 1)
        self.assertEqual(self.release.call_count, 1)

    async def test_failed_acquire_is_not_released(self):
        self._set_mode(PriceSourceMode.REDIS)
        self.acquire.return_value = -1  # Redis error: INCR did not happen
        queue = await self.hub.subscribe("BTWUSDT")

        await self.hub.unsubscribe("BTWUSDT", queue)

        self.release.assert_not_called()

    async def test_silent_redis_feed_starts_local_fallback(self):
        self._set_mode(PriceSourceMode.REDIS)
        with patch.object(hub_mod, "PRICE_FEED_TICK_TIMEOUT_SEC", 0.05):
            queue = await self.hub.subscribe("BTWUSDT")
            await asyncio.sleep(0.2)

        self.local_stream.start.assert_called_once()
        self.request_feed.assert_called_once_with("BTWUSDT")
        self.assertTrue(self.hub._symbols["BTWUSDT"]["local_started"])

        # Local ticks reach the session queue.
        self.hub._publish_local("BTWUSDT", 1.5)
        price = await asyncio.wait_for(queue.get(), timeout=1.0)
        self.assertEqual(price, 1.5)

        await self.hub.unsubscribe("BTWUSDT", queue)
        self.local_stream.stop.assert_called_once()
        self.release.assert_called_once()

    async def test_silent_local_stream_is_recreated(self):
        self._set_mode(PriceSourceMode.LOCAL)
        queue = await self.hub.subscribe("BTWUSDT")
        entry = self.hub._symbols["BTWUSDT"]
        entry["local_last_message"] = 0.0  # local WS went silent

        await self.hub._restart_silent_local_streams()

        self.local_stream.stop.assert_called_once()
        self.assertEqual(self.local_stream.start.call_count, 2)
        self.assertIs(entry["local_stream"], self.local_stream)
        await self.hub.unsubscribe("BTWUSDT", queue)

    async def test_live_local_stream_is_not_recreated(self):
        self._set_mode(PriceSourceMode.LOCAL)
        queue = await self.hub.subscribe("BTWUSDT")

        await self.hub._restart_silent_local_streams()

        self.local_stream.start.assert_called_once()
        self.local_stream.stop.assert_not_called()
        await self.hub.unsubscribe("BTWUSDT", queue)

    async def test_fanout_stops_even_if_cancel_is_swallowed(self):
        self._set_mode(PriceSourceMode.REDIS)
        with patch.object(hub_mod, "PRICE_FEED_TICK_TIMEOUT_SEC", 0.05):
            queue = await self.hub.subscribe("BTWUSDT")
            sub = self.hub._symbols["BTWUSDT"]["queue_subs"][id(queue)]
            fanout = sub.fanout
            await asyncio.sleep(0.01)  # fanout is now inside wait_for
            fanout.cancel = lambda *a, **k: False  # simulate the lost cancellation
            self.local_stream.start.reset_mock()

            await self.hub.unsubscribe("BTWUSDT", queue)
            await asyncio.wait_for(fanout, timeout=1.0)

        self.assertTrue(fanout.done())
        self.local_stream.start.assert_not_called()

    async def test_subscribe_failure_rolls_back_refcount(self):
        self._set_mode(PriceSourceMode.REDIS)
        failing = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch.object(_SilentRedisSubscriber, "start", failing):
            with self.assertRaises(RuntimeError):
                await self.hub.subscribe("BTWUSDT")

        self.acquire.assert_called_once()
        self.release.assert_called_once()
        self.assertEqual(self.hub._symbols, {})


if __name__ == "__main__":
    unittest.main()
