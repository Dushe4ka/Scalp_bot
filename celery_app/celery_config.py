from celery import Celery
from kombu import Queue
from datetime import timedelta
import os
import sys
from pathlib import Path
from celery_app.config import REDIS_URL, RESULT_BACKEND
from bybit_logic.feeds.feed_config import TRADE_ENGINE_COUNT

celery_app = Celery(
    "scalp_bot",
    broker=REDIS_URL,
    backend=RESULT_BACKEND
)

_engine_count = max(1, TRADE_ENGINE_COUNT)
_engine_queues = tuple(
    Queue(f"trade_engine_{i}") for i in range(_engine_count)
)

_subscription_check_hours = float(os.getenv("SUBSCRIPTION_LIFECYCLE_CHECK_HOURS", "12"))

celery_app.conf.update(
    imports=[
        'celery_app.tasks.short_3_limit',
        'celery_app.tasks.short_3_limit_nomulti',
        'celery_app.tasks.engine_execute_trade',
        'celery_app.tasks.hedge_long_short_bu_ts',
        'celery_app.tasks.custom_algo_nomulti',
        'celery_app.tasks.notifications',
        'celery_app.tasks.subscription_lifecycle',
        'celery_app.tasks.api_key_lifecycle',
        'celery_app.worker_signals',
        'demo_showcase.tasks',
    ],
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    enable_utc=True,
    timezone='Europe/Moscow',
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("trade_user"),
        Queue("demo_showcase"),
    ) + _engine_queues,
    beat_schedule={
        "check-subscription-lifecycle": {
            "task": "check_subscription_lifecycle",
            "schedule": timedelta(hours=_subscription_check_hours),
        },
        "check-api-key-lifecycle": {
            "task": "check_api_key_lifecycle",
            "schedule": timedelta(hours=_subscription_check_hours),
        },
    },
)
