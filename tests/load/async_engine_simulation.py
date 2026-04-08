import asyncio
import random
import time
from dataclasses import dataclass


@dataclass
class SimState:
    trade_id: str
    symbol: str
    entry_price: float
    position_qty: float
    trigger_called: bool = False
    pnl_usdt: float = 0.0
    price_change_percent: float = 0.0


class SimSession:
    """
    Упрощенный стенд для нагрузочной проверки event-loop и логики fan-out.
    Не отправляет ордера на биржу.
    """

    def __init__(self, state: SimState, queue: asyncio.Queue[float]) -> None:
        self.state = state
        self.queue = queue
        self.events = 0

    async def run(self, stop_at: float) -> int:
        while time.time() < stop_at:
            try:
                price = await asyncio.wait_for(self.queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            self.events += 1
            self.state.price_change_percent = ((self.state.entry_price - price) / self.state.entry_price) * 100
            self.state.pnl_usdt = (self.state.entry_price - price) * self.state.position_qty
            if self.state.price_change_percent >= 0.6 and not self.state.trigger_called:
                self.state.trigger_called = True
        return self.events


async def producer(queues: list[asyncio.Queue[float]], start_price: float, stop_at: float) -> None:
    price = start_price
    while time.time() < stop_at:
        price += random.uniform(-0.4, 0.4)
        for q in queues:
            if q.full():
                try:
                    q.get_nowait()
                except Exception:
                    pass
            q.put_nowait(price)
        await asyncio.sleep(0.05)


async def run_simulation(session_count: int, seconds: int) -> None:
    stop_at = time.time() + seconds
    queues = [asyncio.Queue(maxsize=200) for _ in range(session_count)]
    sessions = [
        SimSession(
            state=SimState(
                trade_id=f"sim-{idx}",
                symbol="BTCUSDT",
                entry_price=100000.0,
                position_qty=0.001 + (idx % 5) * 0.0001,
            ),
            queue=queues[idx],
        )
        for idx in range(session_count)
    ]

    tasks = [asyncio.create_task(s.run(stop_at)) for s in sessions]
    prod = asyncio.create_task(producer(queues, start_price=100000.0, stop_at=stop_at))
    await asyncio.gather(prod, *tasks)

    total_events = sum(t.result() for t in tasks)
    triggered = sum(1 for s in sessions if s.state.trigger_called)
    print(
        f"simulation_done sessions={session_count} seconds={seconds} "
        f"total_events={total_events} avg_events={total_events / max(session_count,1):.1f} "
        f"triggered={triggered}"
    )


if __name__ == "__main__":
    # Примеры:
    # python3 tests/load/async_engine_simulation.py
    # SESSION_COUNT=300 SIM_SECONDS=30 python3 tests/load/async_engine_simulation.py
    session_count = int(__import__("os").getenv("SESSION_COUNT", "100"))
    sim_seconds = int(__import__("os").getenv("SIM_SECONDS", "20"))
    asyncio.run(run_simulation(session_count=session_count, seconds=sim_seconds))
