"""
Нагрузочный бенчмарк async multiuser-движка (AsyncTradeEngine).

Один OS-процесс, N торговых сессий (asyncio), один demo-аккаунт, разные символы.
Сравнение с tests/load/short_bu_ts_limit_multiprocess_benchmark.py (N процессов × sync).

Требования:
  - .env: DEMO_API_KEY, DEMO_API_SECRET, параметры алгоритма (TRIGGER_*, USDT_AMOUNT, …)
  - Redis (REDIS_URL) — idempotency и snapshots async-движка

Пример:
  python3 tests/load/short_bu_ts_limit_async_benchmark.py --sessions 10 --minutes 5
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

import dotenv

from bybit_logic._update.async_src import short_bu_ts_limit_multiuser as engine_module
from bybit_logic._update.async_src.short_bu_ts_limit_multiuser import get_async_trade_engine
from bybit_logic.bybit_func import session as bybit_session, stop_trade

dotenv.load_dotenv()

SYMBOLS: list[str] = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "MATICUSDT",
    "LTCUSDT",
    "TRXUSDT",
    "ATOMUSDT",
    "UNIUSDT",
    "APTUSDT",
    "NEARUSDT",
    "SUIUSDT",
    "ARBUSDT",
    "OPUSDT",
    "FILUSDT",
    "ETCUSDT",
    "ICPUSDT",
    "INJUSDT",
    "AAVEUSDT",
    "RUNEUSDT",
    "ALGOUSDT",
    "FTMUSDT",
    "EGLDUSDT",
    "VETUSDT",
]


@dataclass
class Sample:
    ts: float
    cpu_percent: float
    rss_mb: float
    vms_mb: float
    active_sessions: int


@dataclass
class SessionLaunch:
    symbol: str
    trade_id: str | None = None
    error: str | None = None


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Переменная окружения {name} не задана")
    return value


def _sum_for_trades() -> float:
    raw = os.getenv("SHORT_BU_TS_LIMIT_USDT_AMOUNT") or os.getenv("USDT_AMOUNT") or os.getenv("TRADE_SUM_USDT")
    if not raw:
        raise RuntimeError("Задайте SHORT_BU_TS_LIMIT_USDT_AMOUNT, USDT_AMOUNT или TRADE_SUM_USDT в .env")
    return float(raw)


def cleanup_demo_trading() -> None:
    """Отмена ордеров и закрытие позиций на demo (как POST /stop_trading_all)."""
    http_session = bybit_session.create_session(use_demo=True)
    stop_trade.stop_all_trading(http_session)


def read_proc_stat(pid: int) -> tuple[float, float, float] | None:
    stat_path = Path(f"/proc/{pid}/stat")
    status_path = Path(f"/proc/{pid}/status")
    if not stat_path.exists() or not status_path.exists():
        return None

    try:
        with stat_path.open("r", encoding="utf-8") as f:
            parts = f.read().strip().split()
        utime_ticks = float(parts[13])
        stime_ticks = float(parts[14])
        ticks_per_sec = float(os.sysconf(os.sysconf_names["SC_CLK_TCK"]))
        total_cpu_seconds = (utime_ticks + stime_ticks) / ticks_per_sec

        rss_kb = 0.0
        vm_kb = 0.0
        with status_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_kb = float(line.split()[1])
                elif line.startswith("VmSize:"):
                    vm_kb = float(line.split()[1])

        return total_cpu_seconds, rss_kb / 1024.0, vm_kb / 1024.0
    except Exception:
        return None


def read_system_cpu_times() -> tuple[int, int] | None:
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            first = f.readline().strip().split()
        if not first or first[0] != "cpu":
            return None
        nums = [int(x) for x in first[1:]]
        idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
        return idle, sum(nums)
    except Exception:
        return None


def read_system_mem_mb() -> tuple[float, float, float] | None:
    mem_total_kb = None
    mem_avail_kb = None
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total_kb = float(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_avail_kb = float(line.split()[1])
        if mem_total_kb is None or mem_avail_kb is None:
            return None
        used_kb = mem_total_kb - mem_avail_kb
        used_percent = (used_kb / mem_total_kb) * 100 if mem_total_kb else 0.0
        return mem_total_kb / 1024.0, used_kb / 1024.0, used_percent
    except Exception:
        return None


def validate_symbols(sessions: int, symbols: list[str]) -> list[str]:
    uniq = list(dict.fromkeys(s.upper().strip() for s in symbols if s.strip()))
    if len(uniq) < sessions:
        raise ValueError(
            f"Недостаточно уникальных монет: нужно минимум {sessions}, доступно {len(uniq)}"
        )
    return uniq[:sessions]


def count_feed_symbols(engine) -> int:
    try:
        return len(engine.feed_hub._feeds)
    except Exception:
        return -1


def write_report(
    out_path: Path,
    started_at: float,
    finished_at: float,
    sessions: int,
    minutes: float,
    interval_sec: float,
    cpu_count: int,
    selected_symbols: list[str],
    launches: list[SessionLaunch],
    samples: list[Sample],
    sys_cpu_samples: list[float],
    sys_mem_used_percent_samples: list[float],
    sys_mem_used_mb_samples: list[float],
    stagger_sec: float,
) -> None:
    duration_sec = finished_at - started_at
    avg_sys_cpu = statistics.fmean(sys_cpu_samples) if sys_cpu_samples else 0.0
    peak_sys_cpu = max(sys_cpu_samples, default=0.0)
    avg_sys_mem_percent = statistics.fmean(sys_mem_used_percent_samples) if sys_mem_used_percent_samples else 0.0
    peak_sys_mem_percent = max(sys_mem_used_percent_samples, default=0.0)
    avg_sys_mem_mb = statistics.fmean(sys_mem_used_mb_samples) if sys_mem_used_mb_samples else 0.0
    peak_sys_mem_mb = max(sys_mem_used_mb_samples, default=0.0)

    proc_cpu = [s.cpu_percent for s in samples]
    proc_rss = [s.rss_mb for s in samples]
    proc_sessions = [s.active_sessions for s in samples]
    avg_cpu = statistics.fmean(proc_cpu) if proc_cpu else 0.0
    peak_cpu = max(proc_cpu, default=0.0)
    avg_rss = statistics.fmean(proc_rss) if proc_rss else 0.0
    peak_rss = max(proc_rss, default=0.0)
    peak_active = max(proc_sessions, default=0)

    lines: list[str] = []
    lines.append("=== SHORT_BU_TS_LIMIT ASYNC ENGINE BENCHMARK REPORT ===")
    lines.append(f"Mode            : AsyncTradeEngine (1 process, N asyncio sessions)")
    lines.append(f"Started at      : {dt.datetime.fromtimestamp(started_at).isoformat(sep=' ', timespec='seconds')}")
    lines.append(f"Finished at     : {dt.datetime.fromtimestamp(finished_at).isoformat(sep=' ', timespec='seconds')}")
    lines.append(f"Duration (sec)  : {duration_sec:.2f}")
    lines.append(f"Requested min   : {minutes}")
    lines.append(f"Sessions        : {sessions}")
    lines.append(f"CPU cores       : {cpu_count}")
    lines.append(f"Sample interval : {interval_sec:.2f} sec")
    lines.append(f"Submit stagger  : {stagger_sec:.2f} sec")
    lines.append(f"Symbols         : {', '.join(selected_symbols)}")
    lines.append("")
    lines.append("=== SESSION LAUNCHES ===")
    for launch in launches:
        if launch.trade_id:
            lines.append(f"[{launch.symbol}] trade_id={launch.trade_id}")
        else:
            lines.append(f"[{launch.symbol}] FAILED: {launch.error}")
    lines.append("")
    lines.append("=== SYSTEM LOAD ===")
    lines.append(f"CPU avg/peak (%)         : {avg_sys_cpu:.2f} / {peak_sys_cpu:.2f}")
    lines.append(f"Memory used avg/peak (%) : {avg_sys_mem_percent:.2f} / {peak_sys_mem_percent:.2f}")
    lines.append(f"Memory used avg/peak MB  : {avg_sys_mem_mb:.2f} / {peak_sys_mem_mb:.2f}")
    lines.append("")
    lines.append("=== ENGINE PROCESS (single PID) ===")
    lines.append(f"Process CPU avg/peak (%)     : {avg_cpu:.2f} / {peak_cpu:.2f}")
    lines.append(f"Process RSS avg/peak (MB)    : {avg_rss:.2f} / {peak_rss:.2f}")
    lines.append(f"Active sessions peak         : {peak_active}")
    lines.append("")
    lines.append("=== NOTES ===")
    lines.append("Compare with multiprocess benchmark: same RSS total vs N×128MB expected for prefork.")
    lines.append("MarketFeedHub: ~1 public WebSocket per unique symbol (not per session).")
    lines.append("Requires Redis for async idempotency keys (trade_cmd:{tg_id}:{symbol}).")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def wait_sessions_idle(engine, timeout_sec: float = 60.0) -> int:
    deadline = time.time() + timeout_sec
    last = engine.running_count()
    while time.time() < deadline:
        last = engine.running_count()
        if last == 0:
            return 0
        time.sleep(1.0)
    return last


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Бенчмарк AsyncTradeEngine: N сессий в одном процессе, demo API."
    )
    parser.add_argument("--sessions", type=int, required=True, help="Сколько торговых сессий запустить.")
    parser.add_argument("--minutes", type=float, required=True, help="Сколько минут собирать метрики.")
    parser.add_argument("--interval", type=float, default=2.0, help="Интервал семплирования (сек).")
    parser.add_argument(
        "--stagger",
        type=float,
        default=0.3,
        help="Пауза между submit_trade (сек), снижает rate limit Bybit. 0 — без паузы.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tests/load/reports/short_bu_ts_limit_async_benchmark.txt",
        help="Путь к txt-отчёту.",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(SYMBOLS),
        help="Монеты через запятую (не меньше --sessions).",
    )
    parser.add_argument(
        "--tg-id",
        type=int,
        default=int(os.getenv("TG_ID", "999001")),
        help="tg_id для всех сессий (разные символы — разные idempotency keys).",
    )
    args = parser.parse_args()

    if args.sessions <= 0:
        raise ValueError("--sessions должен быть > 0")
    if args.minutes <= 0:
        raise ValueError("--minutes должен быть > 0")
    if args.interval <= 0:
        raise ValueError("--interval должен быть > 0")
    if args.stagger < 0:
        raise ValueError("--stagger не может быть < 0")

    engine_module.USE_DEMO = True

    demo_api_key = _require_env("DEMO_API_KEY")
    demo_api_secret = _require_env("DEMO_API_SECRET")
    sum_for_trades = _sum_for_trades()
    name = os.getenv("TG_NAME", "Async Benchmark")

    symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]
    selected_symbols = validate_symbols(args.sessions, symbol_list)

    engine = get_async_trade_engine()
    launches: list[SessionLaunch] = []

    print(f"=== ASYNC BENCHMARK: {args.sessions} sessions, demo, sum={sum_for_trades} USDT ===")

    for symbol in selected_symbols:
        launch = SessionLaunch(symbol=symbol)
        try:
            trade_id = engine.submit_trade(
                symbol=symbol,
                tg_id=args.tg_id,
                name=name,
                api_key=demo_api_key,
                api_secret=demo_api_secret,
                sum_for_trades=sum_for_trades,
            )
            launch.trade_id = trade_id
            print(f"  started {symbol} -> {trade_id}")
        except Exception as exc:
            launch.error = str(exc)
            print(f"  FAILED {symbol}: {exc}")
        launches.append(launch)
        if args.stagger > 0:
            time.sleep(args.stagger)

    pid = os.getpid()
    cpu_count = os.cpu_count() or 1
    samples: list[Sample] = []
    prev_cpu: tuple[float, float] | None = None
    prev_sys = read_system_cpu_times()
    sys_cpu_samples: list[float] = []
    sys_mem_used_percent_samples: list[float] = []
    sys_mem_used_mb_samples: list[float] = []

    started_at = time.time()
    end_at = started_at + args.minutes * 60.0

    try:
        while time.time() < end_at:
            now = time.time()
            stat = read_proc_stat(pid)
            cpu_percent = 0.0
            rss_mb = 0.0
            vms_mb = 0.0
            if stat is not None:
                cpu_total_sec, rss_mb, vms_mb = stat
                if prev_cpu is not None:
                    prev_cpu_sec, prev_ts = prev_cpu
                    dt_sec = max(0.000001, now - prev_ts)
                    cpu_percent = max(0.0, ((cpu_total_sec - prev_cpu_sec) / dt_sec) * 100.0)
                prev_cpu = (cpu_total_sec, now)

            active = engine.running_count()
            feeds = count_feed_symbols(engine)
            samples.append(
                Sample(ts=now, cpu_percent=cpu_percent, rss_mb=rss_mb, vms_mb=vms_mb, active_sessions=active)
            )
            if feeds >= 0:
                print(
                    f"[sample] cpu={cpu_percent:.1f}% rss={rss_mb:.0f}MB "
                    f"sessions={active} ws_feeds={feeds}",
                    flush=True,
                )

            sys_now = read_system_cpu_times()
            if prev_sys is not None and sys_now is not None:
                idle_prev, total_prev = prev_sys
                idle_now, total_now = sys_now
                total_delta = total_now - total_prev
                idle_delta = idle_now - idle_prev
                if total_delta > 0:
                    busy = (1.0 - idle_delta / total_delta) * 100.0
                    sys_cpu_samples.append(max(0.0, min(100.0, busy)))
            if sys_now is not None:
                prev_sys = sys_now

            mem = read_system_mem_mb()
            if mem is not None:
                _total_mb, used_mb, used_percent = mem
                sys_mem_used_mb_samples.append(used_mb)
                sys_mem_used_percent_samples.append(used_percent)

            time.sleep(args.interval)
    finally:
        print("Останавливаем demo-торговлю на Bybit (ордера + позиции)...")
        try:
            cleanup_demo_trading()
            print("Demo-торговля остановлена.")
        except Exception as exc:
            print(f"WARNING: stop_all_trading: {exc}")

        remaining = wait_sessions_idle(engine, timeout_sec=90.0)
        if remaining > 0:
            print(f"WARNING: после cleanup осталось active sessions: {remaining}")

    finished_at = time.time()
    write_report(
        out_path=Path(args.output),
        started_at=started_at,
        finished_at=finished_at,
        sessions=args.sessions,
        minutes=args.minutes,
        interval_sec=args.interval,
        cpu_count=cpu_count,
        selected_symbols=selected_symbols,
        launches=launches,
        samples=samples,
        sys_cpu_samples=sys_cpu_samples,
        sys_mem_used_percent_samples=sys_mem_used_percent_samples,
        sys_mem_used_mb_samples=sys_mem_used_mb_samples,
        stagger_sec=args.stagger,
    )

    report_path = Path(args.output).resolve()
    print(f"Benchmark finished. Report saved to: {report_path}")


if __name__ == "__main__":
    main()
