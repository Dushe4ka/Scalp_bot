"""
Trade routing across Celery engine workers (Phase 2).

Each engine worker: one queue trade_engine_{id}, concurrency=1, max MAX_SESSIONS_PER_ENGINE.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from bybit_logic.feeds.feed_config import MAX_SESSIONS_PER_ENGINE, TRADE_ENGINE_COUNT
from celery_app.config import REDIS_URL
from logger_config import setup_logger

logger = setup_logger(__name__)

KEY_ENGINE_IDS = "engine:ids"
KEY_ENGINE_PENDING = "engine:pending"
ENGINE_ALIVE_TTL_SEC = 30
ENGINE_HEARTBEAT_INTERVAL_SEC = 5

_ASSIGN_LUA = """
local max_load = tonumber(ARGV[1])
local best_id = nil
local best_load = max_load + 1
for i = 2, #ARGV do
  local eid = ARGV[i]
  local load_key = 'engine:' .. eid .. ':load'
  local alive_key = 'engine:' .. eid .. ':alive'
  local alive = redis.call('GET', alive_key)
  if alive then
    local load = tonumber(redis.call('GET', load_key) or '0')
    if load < max_load and load < best_load then
      best_load = load
      best_id = eid
    end
  end
end
if not best_id then
  return {nil, tostring(best_load)}
end
local load_key = 'engine:' .. best_id .. ':load'
local new_load = redis.call('INCR', load_key)
if new_load > max_load then
  redis.call('DECR', load_key)
  return {nil, tostring(new_load)}
end
return {best_id, tostring(new_load)}
"""


def _client():
    import redis

    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def engine_queue_name(engine_id: int | str) -> str:
    return f"trade_engine_{int(engine_id)}"


def _engine_key(engine_id: int | str, suffix: str) -> str:
    return f"engine:{int(engine_id)}:{suffix}"


def ensure_engine_registry(count: int | None = None) -> list[str]:
    n = count if count is not None else TRADE_ENGINE_COUNT
    client = _client()
    ids = [str(i) for i in range(n)]
    for eid in ids:
        client.sadd(KEY_ENGINE_IDS, eid)
        client.set(_engine_key(eid, "max_load"), MAX_SESSIONS_PER_ENGINE)
        if client.get(_engine_key(eid, "load")) is None:
            client.set(_engine_key(eid, "load"), 0)
    return ids


def register_engine(engine_id: int | str) -> None:
    eid = str(int(engine_id))
    client = _client()
    client.sadd(KEY_ENGINE_IDS, eid)
    client.set(_engine_key(eid, "max_load"), MAX_SESSIONS_PER_ENGINE)
    if client.get(_engine_key(eid, "load")) is None:
        client.set(_engine_key(eid, "load"), 0)
    touch_engine_alive(eid)
    logger.info("Engine %s registered in orchestrator", eid)


def touch_engine_alive(engine_id: int | str) -> None:
    client = _client()
    client.set(_engine_key(engine_id, "alive"), str(time.time()), ex=ENGINE_ALIVE_TTL_SEC)


def get_engine_load(engine_id: int | str) -> int:
    client = _client()
    return int(client.get(_engine_key(engine_id, "load")) or 0)


def get_all_engine_loads() -> dict[str, int]:
    client = _client()
    ids = client.smembers(KEY_ENGINE_IDS) or []
    out: dict[str, int] = {}
    for eid in sorted(ids, key=lambda x: int(x)):
        out[eid] = int(client.get(_engine_key(eid, "load")) or 0)
    return out


def release_engine_slot(engine_id: int | str | None = None) -> None:
    eid = engine_id if engine_id is not None else os.getenv("CELERY_ENGINE_ID")
    if eid is None or str(eid).strip() == "":
        return
    client = _client()
    key = _engine_key(eid, "load")
    val = client.decr(key)
    if val is not None and int(val) < 0:
        client.set(key, 0)


def assign_trade(
    *,
    symbol: str,
    tg_id: int,
    name: str,
    api_key: str,
    api_secret: str,
    sum_for_trades: float,
    trade_id: str | None = None,
) -> dict[str, Any]:
    """
    Pick least-loaded alive engine and reserve a slot (INCR load).
    Returns dict with engine_id, trade_id, status.
    """
    ensure_engine_registry()
    client = _client()
    trade_id = trade_id or f"{tg_id}:{symbol.upper()}:{uuid.uuid4().hex[:10]}"
    ids = sorted(client.smembers(KEY_ENGINE_IDS) or [], key=lambda x: int(x))
    if not ids:
        return {"status": "error", "error": "no engines registered", "trade_id": trade_id}

    result = client.eval(_ASSIGN_LUA, 0, str(MAX_SESSIONS_PER_ENGINE), *ids)
    if not result or result[0] is None:
        payload = {
            "trade_id": trade_id,
            "symbol": symbol.upper(),
            "tg_id": tg_id,
            "name": name,
            "api_key": api_key,
            "api_secret": api_secret,
            "sum_for_trades": sum_for_trades,
            "ts": time.time(),
        }
        client.rpush(KEY_ENGINE_PENDING, json.dumps(payload))
        return {"status": "queued", "trade_id": trade_id, "engine_id": None}

    engine_id = str(result[0])
    return {
        "status": "assigned",
        "trade_id": trade_id,
        "engine_id": engine_id,
        "queue": engine_queue_name(engine_id),
        "load": int(result[1]),
    }


def reaper_stale_engines(stale_sec: float = 60.0) -> list[str]:
    """Reset load for engines without recent heartbeat."""
    client = _client()
    reset: list[str] = []
    now = time.time()
    for eid in client.smembers(KEY_ENGINE_IDS) or []:
        alive_raw = client.get(_engine_key(eid, "alive"))
        if not alive_raw:
            client.set(_engine_key(eid, "load"), 0)
            reset.append(str(eid))
            continue
        try:
            if now - float(alive_raw) > stale_sec:
                client.set(_engine_key(eid, "load"), 0)
                reset.append(str(eid))
        except ValueError:
            client.set(_engine_key(eid, "load"), 0)
            reset.append(str(eid))
    return reset


def pop_pending_trade() -> dict[str, Any] | None:
    client = _client()
    raw = client.lpop(KEY_ENGINE_PENDING)
    if not raw:
        return None
    return json.loads(raw)
