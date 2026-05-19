"""Celery worker lifecycle hooks for trade engine workers."""
from __future__ import annotations

import os
import threading
import time

from celery.signals import worker_process_init, worker_process_shutdown

from celery_app.trade_orchestrator import (
    ENGINE_HEARTBEAT_INTERVAL_SEC,
    register_engine,
    touch_engine_alive,
)
from logger_config import setup_logger

logger = setup_logger(__name__)

_heartbeat_stop = threading.Event()
_heartbeat_thread: threading.Thread | None = None


def _heartbeat_loop(engine_id: str) -> None:
    while not _heartbeat_stop.is_set():
        try:
            touch_engine_alive(engine_id)
        except Exception as e:
            logger.warning("Engine heartbeat failed: %s", e)
        _heartbeat_stop.wait(ENGINE_HEARTBEAT_INTERVAL_SEC)


@worker_process_init.connect
def on_worker_process_init(**kwargs) -> None:
    engine_id = os.getenv("CELERY_ENGINE_ID")
    if engine_id is None or str(engine_id).strip() == "":
        return
    eid = str(int(engine_id))
    register_engine(eid)
    global _heartbeat_thread
    _heartbeat_stop.clear()
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(eid,),
        name=f"engine-heartbeat-{eid}",
        daemon=True,
    )
    _heartbeat_thread.start()
    logger.info("Trade engine worker process init: CELERY_ENGINE_ID=%s", eid)


@worker_process_shutdown.connect
def on_worker_process_shutdown(**kwargs) -> None:
    _heartbeat_stop.set()
