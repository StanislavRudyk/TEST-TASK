

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import async_session

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def _scheduled_collect() -> None:
    """Job function: collect all tracked channels."""
    from app.collector import collect_all_channels  

    logger.info("Scheduled collection started")
    async with async_session() as session:
        summary = await collect_all_channels(session)
    logger.info("Scheduled collection finished: %s", summary)

def start_scheduler() -> None:
    """Start the background scheduler (called once at app startup)."""
    interval = settings.collect_interval_minutes
    scheduler.add_job(
        _scheduled_collect,
        trigger=IntervalTrigger(minutes=interval),
        id="collect_all",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started — collecting every %d minutes", interval)

def stop_scheduler() -> None:
    """Graceful shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
