from celery import Celery
from kombu import Queue
import os
import sys
from pathlib import Path
from celery_app.config import REDIS_URL, RESULT_BACKEND

celery_app = Celery(
    "scalp_bot",
    broker=REDIS_URL,
    backend=RESULT_BACKEND
)

celery_app.conf.update(
    imports=[
        'celery_app.tasks.short_3_limit',
        'celery_app.tasks.short_bu_ts_limit_nomulti',
        'celery_app.tasks.hedge_long_short_bu_ts',
        'celery_app.tasks.notifications',
    ],
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    enable_utc=True,
    timezone='Europe/Moscow',
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("trade_user"),
    ),
)