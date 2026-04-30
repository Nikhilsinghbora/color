"""Celery application configuration with Redis broker.

Configures task routing to dedicated queues, serialization,
and Celery Beat schedule for all periodic tasks.

Requirements: 1.1, 1.3, 1.4, 13.6
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "color_prediction",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task routing to dedicated queues
    task_routes={
        "app.tasks.wallet_tasks.*": {"queue": "wallet"},
        "app.tasks.email_tasks.*": {"queue": "email"},
        "app.tasks.game_tasks.*": {"queue": "game"},
        "app.tasks.report_tasks.*": {"queue": "reports"},
        "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
        # Leaderboard updates go to analytics queue
        "app.tasks.leaderboard_tasks.*": {"queue": "analytics"},
    },
    # Default queue for anything not explicitly routed
    task_default_queue="default",
    # Celery Beat periodic task schedule
    beat_schedule={
        "advance-game-round": {
            "task": "app.tasks.game_tasks.advance_game_round",
            "schedule": 3.0,  # every 3 seconds
        },
        "reset-deposit-limits": {
            "task": "app.tasks.maintenance_tasks.reset_deposit_limits",
            "schedule": 60.0,  # every 60 seconds
        },
        "generate-daily-report": {
            "task": "app.tasks.report_tasks.generate_daily_report",
            "schedule": crontab(hour=0, minute=0),  # daily at 00:00 UTC
        },
        "cleanup-expired-sessions": {
            "task": "app.tasks.maintenance_tasks.cleanup_expired_sessions",
            "schedule": 300.0,  # every 5 minutes
        },
    },
)

# Auto-discover tasks in app/tasks/ package
celery_app.autodiscover_tasks(["app.tasks"])
