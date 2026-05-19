"""
Phase 2 benchmark: orchestrator load distribution + optional demo execution.

Modes:
  orchestrator — assign N virtual trades, verify engine:*:load in Redis (no Bybit)
  demo         — assign + run engine_execute via Celery (requires workers + demo keys)

Examples:
  # Distribution only (2 engines, 60 slots):
  python -m tests.load.phase2_sharding_benchmark --sessions 60 --mode orchestrator

  # With demo trading (start feed + 2 engine workers first, see tests/load/README.md):
  python -m tests.load.phase2_sharding_benchmark --sessions 30 --mode demo --minutes 2
"""
from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import dotenv

dotenv.load_dotenv()


@dataclass
class Sample:
    ts: float
    engine_loads: dict[str, int]
    feed_status: str


def _read_proc_rss_mb(pid: int) -> float | None:
    status = Path(f"/proc/{pid}/status")
    if not status.exists():
        return None
    for line in status.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return float(line.split()[1]) / 1024.0
    return None


def _find_celery_engine_pids() -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-f", "trade_engine_"], text=True)
        return [int(x) for x in out.split() if x.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return []


def run_orchestrator_benchmark(sessions: int, engine_count: int) -> dict:
    from celery_app.trade_orchestrator import (
        assign_trade,
        ensure_engine_registry,
        get_all_engine_loads,
        register_engine,
        reaper_stale_engines,
    )

    ensure_engine_registry(engine_count)
    for i in range(engine_count):
        register_engine(i)

    results = []
    for i in range(sessions):
        r = assign_trade(
            symbol="BTCUSDT",
            tg_id=900000 + i,
            name="bench",
            api_key=f"key{i}",
            api_secret=f"sec{i}",
            sum_for_trades=10.0,
        )
        results.append(r)

    loads = get_all_engine_loads()
    assigned = sum(1 for r in results if r.get("status") == "assigned")
    queued = sum(1 for r in results if r.get("status") == "queued")

    import redis
    from celery_app.config import REDIS_URL

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    for eid in loads:
        client.set(f"engine:{eid}:load", 0)

    return {
        "assigned": assigned,
        "queued": queued,
        "loads": loads,
        "max_per_engine": max(loads.values()) if loads else 0,
        "engine_count": engine_count,
    }


def run_demo_benchmark(sessions: int, minutes: float, stagger: float) -> None:
    from celery_app.trade_orchestrator import ensure_engine_registry, get_all_engine_loads, register_engine
    from celery_app.tasks.short_3_limit import short_3_limit

    engine_count = int(os.getenv("TRADE_ENGINE_COUNT", "2"))
    ensure_engine_registry(engine_count)
    for i in range(engine_count):
        register_engine(i)

    demo_key = os.getenv("DEMO_API_KEY")
    demo_secret = os.getenv("DEMO_API_SECRET")
    if not demo_key or not demo_secret:
        raise RuntimeError("DEMO_API_KEY / DEMO_API_SECRET required for demo mode")

    for i in range(sessions):
        short_3_limit.apply_async(
            kwargs={
                "symbol": "BTCUSDT" if i % 2 == 0 else "ETHUSDT",
                "tg_id": 800000 + i,
                "name": "phase2_bench",
                "api_key": demo_key,
                "api_secret": demo_secret,
                "sum_for_trades": float(os.getenv("USDT_AMOUNT", "10")),
            },
            countdown=i * stagger,
        )
        if stagger > 0:
            time.sleep(stagger)

    samples: list[Sample] = []
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        from bybit_logic.feeds.redis_market_keys import KEY_FEED_STATUS
        import redis
        from celery_app.config import REDIS_URL

        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        samples.append(
            Sample(
                ts=time.time(),
                engine_loads=get_all_engine_loads(),
                feed_status=client.get(KEY_FEED_STATUS) or "unknown",
            )
        )
        time.sleep(2.0)

    report_path = Path("tests/load/reports") / f"phase2_sharding_{sessions}.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "=== PHASE 2 SHARDING BENCHMARK (demo) ===",
        f"Sessions requested: {sessions}",
        f"TRADE_ENGINE_COUNT: {engine_count}",
        f"Duration: {minutes} min",
        "",
        "=== Engine loads (last sample) ===",
    ]
    if samples:
        for eid, load in sorted(samples[-1].engine_loads.items(), key=lambda x: int(x[0])):
            lines.append(f"  engine:{eid}:load = {load}")
        lines.append(f"  feed status = {samples[-1].feed_status}")
    pids = _find_celery_engine_pids()
    lines.extend(["", "=== Celery engine PIDs (RSS MB) ==="])
    for pid in pids:
        rss = _read_proc_rss_mb(pid)
        lines.append(f"  pid={pid} rss={rss:.1f} MB" if rss else f"  pid={pid}")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {report_path}")


def write_orchestrator_report(sessions: int, summary: dict) -> None:
    report_path = Path("tests/load/reports") / f"phase2_orchestrator_{sessions}.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "=== PHASE 2 ORCHESTRATOR BENCHMARK ===",
        f"Sessions: {sessions}",
        f"Engine count: {summary['engine_count']}",
        f"Assigned: {summary['assigned']}",
        f"Queued: {summary['queued']}",
        f"Max load on one engine: {summary['max_per_engine']}",
        "",
        "Per-engine load:",
    ]
    for eid, load in sorted(summary["loads"].items(), key=lambda x: int(x[0])):
        lines.append(f"  engine:{eid}:load = {load}")
    cap = int(os.getenv("MAX_SESSIONS_PER_ENGINE", "30"))
    ok = summary["max_per_engine"] <= cap and summary["assigned"] == min(
        sessions, summary["engine_count"] * cap
    )
    lines.append("")
    lines.append(f"Sharding OK (max <= {cap} per engine): {ok}")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {report_path}")
    if not ok:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 sharding benchmark")
    parser.add_argument("--sessions", type=int, default=60)
    parser.add_argument("--mode", choices=["orchestrator", "demo"], default="orchestrator")
    parser.add_argument("--minutes", type=float, default=2.0)
    parser.add_argument("--stagger", type=float, default=0.1)
    parser.add_argument("--engine-count", type=int, default=None)
    args = parser.parse_args()

    engine_count = args.engine_count or int(os.getenv("TRADE_ENGINE_COUNT", "2"))
    os.environ["TRADE_ENGINE_COUNT"] = str(engine_count)

    if args.mode == "orchestrator":
        summary = run_orchestrator_benchmark(args.sessions, engine_count)
        write_orchestrator_report(args.sessions, summary)
    else:
        run_demo_benchmark(args.sessions, args.minutes, args.stagger)


if __name__ == "__main__":
    main()
