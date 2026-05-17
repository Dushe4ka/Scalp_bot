import argparse
import datetime as dt
import multiprocessing as mp
import os
import signal
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from bybit_logic.api_algorithms.short_bu_ts_limit import start_trading
from bybit_logic.bybit_func import session as bybit_session, stop_trade


# Можно расширять список монет под вашу стратегию.
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
class ProcSample:
    ts: float
    cpu_percent: float
    rss_mb: float
    vms_mb: float


@dataclass
class ProcSummary:
    pid: int
    symbol: str
    start_ok: bool = False
    start_error: str | None = None
    samples: list[ProcSample] = field(default_factory=list)

    def avg_cpu(self) -> float:
        return statistics.fmean(s.cpu_percent for s in self.samples) if self.samples else 0.0

    def peak_cpu(self) -> float:
        return max((s.cpu_percent for s in self.samples), default=0.0)

    def avg_rss(self) -> float:
        return statistics.fmean(s.rss_mb for s in self.samples) if self.samples else 0.0

    def peak_rss(self) -> float:
        return max((s.rss_mb for s in self.samples), default=0.0)

    def avg_vms(self) -> float:
        return statistics.fmean(s.vms_mb for s in self.samples) if self.samples else 0.0

    def peak_vms(self) -> float:
        return max((s.vms_mb for s in self.samples), default=0.0)


def trading_worker(symbol: str) -> None:
    start_trading(symbol, use_demo=True)


def cleanup_demo_trading() -> None:
    """Отмена ордеров и закрытие позиций на demo (как POST /stop_trading_all)."""
    http_session = bybit_session.create_session(use_demo=True)
    stop_trade.stop_all_trading(http_session)


def read_proc_stat(pid: int) -> tuple[float, float] | None:
    """
    Возвращает:
      - total_cpu_seconds (user + system)
      - rss_mb
    """
    stat_path = Path(f"/proc/{pid}/stat")
    status_path = Path(f"/proc/{pid}/status")
    if not stat_path.exists() or not status_path.exists():
        return None

    try:
        with stat_path.open("r", encoding="utf-8") as f:
            content = f.read().strip()
        parts = content.split()
        # utime=14, stime=15 в /proc/<pid>/stat (индексы 13,14)
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
    """
    Возвращает (idle, total) тики CPU по /proc/stat.
    """
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            first = f.readline().strip().split()
        if not first or first[0] != "cpu":
            return None
        nums = [int(x) for x in first[1:]]
        idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
        total = sum(nums)
        return idle, total
    except Exception:
        return None


def read_system_mem_mb() -> tuple[float, float, float] | None:
    """
    Возвращает:
      - total_mb
      - used_mb
      - used_percent
    """
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


def validate_symbols(processes: int, symbols: list[str]) -> None:
    uniq = list(dict.fromkeys(s.upper().strip() for s in symbols if s.strip()))
    if len(uniq) < processes:
        raise ValueError(
            f"Недостаточно уникальных монет в SYMBOLS: нужно минимум {processes}, доступно {len(uniq)}"
        )


def write_report(
    out_path: Path,
    started_at: float,
    finished_at: float,
    processes: int,
    minutes: float,
    interval_sec: float,
    cpu_count: int,
    selected_symbols: list[str],
    proc_summaries: list[ProcSummary],
    sys_cpu_samples: list[float],
    sys_mem_used_percent_samples: list[float],
    sys_mem_used_mb_samples: list[float],
) -> None:
    duration_sec = finished_at - started_at
    avg_sys_cpu = statistics.fmean(sys_cpu_samples) if sys_cpu_samples else 0.0
    peak_sys_cpu = max(sys_cpu_samples, default=0.0)
    avg_sys_mem_percent = statistics.fmean(sys_mem_used_percent_samples) if sys_mem_used_percent_samples else 0.0
    peak_sys_mem_percent = max(sys_mem_used_percent_samples, default=0.0)
    avg_sys_mem_mb = statistics.fmean(sys_mem_used_mb_samples) if sys_mem_used_mb_samples else 0.0
    peak_sys_mem_mb = max(sys_mem_used_mb_samples, default=0.0)

    total_avg_proc_cpu = sum(p.avg_cpu() for p in proc_summaries)
    total_peak_proc_cpu = sum(p.peak_cpu() for p in proc_summaries)
    total_avg_proc_rss = sum(p.avg_rss() for p in proc_summaries)
    total_peak_proc_rss = sum(p.peak_rss() for p in proc_summaries)

    lines: list[str] = []
    lines.append("=== SHORT_BU_TS_LIMIT MULTIPROCESS BENCHMARK REPORT ===")
    lines.append(f"Started at      : {dt.datetime.fromtimestamp(started_at).isoformat(sep=' ', timespec='seconds')}")
    lines.append(f"Finished at     : {dt.datetime.fromtimestamp(finished_at).isoformat(sep=' ', timespec='seconds')}")
    lines.append(f"Duration (sec)  : {duration_sec:.2f}")
    lines.append(f"Requested min   : {minutes}")
    lines.append(f"Processes       : {processes}")
    lines.append(f"CPU cores       : {cpu_count}")
    lines.append(f"Sample interval : {interval_sec:.2f} sec")
    lines.append(f"Symbols         : {', '.join(selected_symbols)}")
    lines.append("")
    lines.append("=== SYSTEM LOAD ===")
    lines.append(f"CPU avg/peak (%)         : {avg_sys_cpu:.2f} / {peak_sys_cpu:.2f}")
    lines.append(f"Memory used avg/peak (%) : {avg_sys_mem_percent:.2f} / {peak_sys_mem_percent:.2f}")
    lines.append(f"Memory used avg/peak MB  : {avg_sys_mem_mb:.2f} / {peak_sys_mem_mb:.2f}")
    lines.append("")
    lines.append("=== AGGREGATED PROCESS LOAD (sum by workers) ===")
    lines.append(f"Workers CPU avg/peak (%)  : {total_avg_proc_cpu:.2f} / {total_peak_proc_cpu:.2f}")
    lines.append(f"Workers RSS avg/peak (MB) : {total_avg_proc_rss:.2f} / {total_peak_proc_rss:.2f}")
    lines.append("")
    lines.append("=== PER PROCESS ===")
    for s in proc_summaries:
        lines.append(
            f"[{s.symbol}] pid={s.pid} start_ok={s.start_ok} "
            f"avg_cpu={s.avg_cpu():.2f}% peak_cpu={s.peak_cpu():.2f}% "
            f"avg_rss={s.avg_rss():.2f}MB peak_rss={s.peak_rss():.2f}MB "
            f"avg_vms={s.avg_vms():.2f}MB peak_vms={s.peak_vms():.2f}MB "
            f"samples={len(s.samples)}"
        )
        if s.start_error:
            lines.append(f"  start_error: {s.start_error}")
    lines.append("")
    lines.append("=== ESTIMATION ===")
    if processes > 0:
        cpu_per_proc = total_avg_proc_cpu / processes
        rss_per_proc = total_avg_proc_rss / processes
        lines.append(f"Estimated avg CPU per process (%): {cpu_per_proc:.2f}")
        lines.append(f"Estimated avg RSS per process (MB): {rss_per_proc:.2f}")
        lines.append("Use your server free CPU/RAM with safety margin 20-30% to estimate max process count.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Запуск N процессов short_bu_ts_limit и сбор метрик за M минут."
    )
    parser.add_argument("--processes", type=int, required=True, help="Сколько процессов запустить.")
    parser.add_argument("--minutes", type=float, required=True, help="Сколько минут собирать метрики.")
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Интервал семплирования метрик (сек). По умолчанию 2.0",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tests/load/reports/short_bu_ts_limit_benchmark.txt",
        help="Путь к txt-отчету.",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(SYMBOLS),
        help="Список монет через запятую. Должно быть не меньше, чем --processes.",
    )
    args = parser.parse_args()

    if args.processes <= 0:
        raise ValueError("--processes должен быть > 0")
    if args.minutes <= 0:
        raise ValueError("--minutes должен быть > 0")
    if args.interval <= 0:
        raise ValueError("--interval должен быть > 0")

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    validate_symbols(args.processes, symbols)
    selected_symbols = symbols[: args.processes]

    procs: list[tuple[str, mp.Process]] = []
    summaries: list[ProcSummary] = []

    for symbol in selected_symbols:
        p = mp.Process(target=trading_worker, args=(symbol,), daemon=False)
        p.start()
        procs.append((symbol, p))
        summaries.append(ProcSummary(pid=p.pid or -1, symbol=symbol, start_ok=p.pid is not None))

    end_at = time.time() + args.minutes * 60.0
    prev_proc_cpu: dict[int, tuple[float, float]] = {}
    cpu_count = os.cpu_count() or 1

    prev_sys = read_system_cpu_times()
    sys_cpu_samples: list[float] = []
    sys_mem_used_percent_samples: list[float] = []
    sys_mem_used_mb_samples: list[float] = []
    started_at = time.time()

    try:
        while time.time() < end_at:
            now = time.time()
            for summary in summaries:
                if summary.pid <= 0:
                    continue
                stat = read_proc_stat(summary.pid)
                if stat is None:
                    continue
                cpu_total_sec, rss_mb, vms_mb = stat
                prev = prev_proc_cpu.get(summary.pid)
                cpu_percent = 0.0
                if prev is not None:
                    prev_cpu_sec, prev_ts = prev
                    dt_sec = max(0.000001, now - prev_ts)
                    cpu_percent = max(0.0, ((cpu_total_sec - prev_cpu_sec) / dt_sec) * 100.0)
                prev_proc_cpu[summary.pid] = (cpu_total_sec, now)
                summary.samples.append(
                    ProcSample(
                        ts=now,
                        cpu_percent=cpu_percent,
                        rss_mb=rss_mb,
                        vms_mb=vms_mb,
                    )
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
        # 1) Сначала биржа: отмена ордеров и закрытие позиций (пока процессы ещё живы).
        print("Останавливаем demo-торговлю на Bybit (ордера + позиции)...")
        try:
            cleanup_demo_trading()
            print("Demo-торговля остановлена: ордера отменены, позиции закрыты.")
        except Exception as exc:
            print(f"WARNING: не удалось выполнить stop_all_trading: {exc}")

        # 2) Затем алгоритмы: SIGINT → завершение WebSocket и процессов.
        for _, proc in procs:
            if proc.is_alive():
                try:
                    os.kill(proc.pid, signal.SIGINT)
                except Exception:
                    pass

        time.sleep(2.0)

        for _, proc in procs:
            if proc.is_alive():
                proc.terminate()
        for _, proc in procs:
            proc.join(timeout=5.0)
        for _, proc in procs:
            if proc.is_alive():
                proc.kill()

    finished_at = time.time()
    write_report(
        out_path=Path(args.output),
        started_at=started_at,
        finished_at=finished_at,
        processes=args.processes,
        minutes=args.minutes,
        interval_sec=args.interval,
        cpu_count=cpu_count,
        selected_symbols=selected_symbols,
        proc_summaries=summaries,
        sys_cpu_samples=sys_cpu_samples,
        sys_mem_used_percent_samples=sys_mem_used_percent_samples,
        sys_mem_used_mb_samples=sys_mem_used_mb_samples,
    )

    report_path = Path(args.output).resolve()
    print(f"Benchmark finished. Report saved to: {report_path}")


if __name__ == "__main__":
    # Пример (всегда demo API: use_demo=True):
    # python3 tests/load/short_bu_ts_limit_multiprocess_benchmark.py --processes 3 --minutes 5
    main()
