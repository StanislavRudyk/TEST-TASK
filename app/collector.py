

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIAnalysis,
    Channel,
    ChannelMetricsSnapshot,
    Post,
    PostMetricsSnapshot,
)
from app.scraper import (
    ChannelNotFoundError,
    ChannelPrivateError,
    ScrapedChannel,
    ScrapedPost,
    scrape_channel,
)
from app import ai_service

logger = logging.getLogger(__name__)

async def add_channel(session: AsyncSession, username: str) -> Channel:
    """
    Add a new channel: create DB row, trigger first scrape.

    If channel already exists, return existing row.
    """
    username = username.strip().lstrip("@").lower()

    existing = await session.get(Channel, username)
    if existing is not None:
        return existing

    channel = Channel(username=username, status="pending")
    session.add(channel)
    await session.commit()
    await session.refresh(channel)

    await collect_channel(session, username)

    return channel

async def collect_channel(session: AsyncSession, username: str) -> bool:
    """
    Scrape channel and upsert data.  Returns True on success.

    Designed to be called both on-demand (add) and periodically (scheduler).
    """

    await session.execute(
        update(Channel)
        .where(Channel.username == username)
        .values(status="collecting", error_message=None)
    )
    await session.commit()

    try:
        scraped = await scrape_channel(username)
    except ChannelNotFoundError:
        await _mark_error(session, username, "Channel not found")
        return False
    except ChannelPrivateError:
        await _mark_error(session, username, "Channel is private")
        return False
    except Exception as exc:
        logger.exception("Collection failed for @%s", username)
        await _mark_error(session, username, f"Scraping error: {exc}")
        return False

    await session.execute(
        update(Channel)
        .where(Channel.username == username)
        .values(
            title=scraped.title,
            description=scraped.description,
            avatar_url=scraped.avatar_url,
            subscriber_count=scraped.subscriber_count,
            status="active",
            last_collected_at=dt.datetime.now(dt.timezone.utc),
            error_message=None,
        )
    )

    if scraped.subscriber_count is not None:
        session.add(ChannelMetricsSnapshot(
            channel_username=username,
            subscriber_count=scraped.subscriber_count,
        ))

    for sp in scraped.posts:
        await _upsert_post(session, username, sp)

    await session.commit()

    try:
        await _ai_process_posts(session, username)
    except Exception:
        logger.exception("AI processing failed for @%s (non-critical)", username)

    logger.info(
        "Collected @%s: %d posts, subscribers=%s",
        username,
        len(scraped.posts),
        scraped.subscriber_count,
    )
    return True

async def collect_all_channels(session: AsyncSession) -> dict:
    """Collect data for all tracked channels.  Returns summary."""
    result = await session.execute(
        select(Channel.username).where(Channel.status != "error")
    )
    usernames = [row[0] for row in result.all()]

    summary = {"total": len(usernames), "success": 0, "failed": 0}
    for uname in usernames:
        ok = await collect_channel(session, uname)
        if ok:
            summary["success"] += 1
        else:
            summary["failed"] += 1

    logger.info("Collection round complete: %s", summary)
    return summary

async def _upsert_post(
    session: AsyncSession,
    channel_username: str,
    sp: ScrapedPost,
) -> None:
    """
    Insert or update a post using ON CONFLICT on the natural key.

    On conflict: update views, reactions (they change over time),
    but keep the original text and date.
    """
    stmt = pg_insert(Post).values(
        channel_username=channel_username,
        message_id=sp.message_id,
        text=sp.text,
        date=sp.date,
        views=sp.views,
        reactions=sp.reactions,
        media_type=sp.media_type,
        url=sp.url,
    )

    stmt = stmt.on_conflict_do_update(
        constraint="uq_post_natural_key",
        set_={
            "views": stmt.excluded.views,
            "reactions": stmt.excluded.reactions,
        },
    )

    result = await session.execute(stmt)

    post_row = await session.execute(
        select(Post.id).where(
            Post.channel_username == channel_username,
            Post.message_id == sp.message_id,
        )
    )
    post_id = post_row.scalar_one_or_none()
    if post_id is not None:
        session.add(PostMetricsSnapshot(
            post_id=post_id,
            views=sp.views,
            reactions=sp.reactions,
        ))

async def _mark_error(session: AsyncSession, username: str, message: str) -> None:
    """Mark channel status as error with a human-readable message."""
    await session.execute(
        update(Channel)
        .where(Channel.username == username)
        .values(status="error", error_message=message)
    )
    await session.commit()
    logger.warning("Channel @%s error: %s", username, message)

async def _ai_process_posts(session: AsyncSession, channel_username: str) -> None:
    """Categorise posts that don't have an AI category yet (best-effort)."""
    if not ai_service.is_ai_available():
        return

    result = await session.execute(
        select(Post)
        .where(
            Post.channel_username == channel_username,
            Post.ai_category.is_(None),
            Post.text.isnot(None),
        )
        .order_by(Post.date.desc())
        .limit(10)  
    )
    posts = result.scalars().all()

    for post in posts:
        if post.text and len(post.text.strip()) > 10:
            category = await ai_service.categorise_post(post.text)
            if category:
                post.ai_category = category[:128]

    await session.commit()
