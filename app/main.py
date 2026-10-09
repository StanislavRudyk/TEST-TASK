"""
channel-radar — FastAPI application.

Routes:
  GET  /                     → dashboard (channel list)
  POST /api/channels         → add a channel
  GET  /channel/<username>   → channel detail page
  GET  /post/<username>/<id> → post detail page
  GET  /api/channels/<u>/digest → AI digest
  GET  /api/health           → health check
  GET  /api/collect          → trigger manual collection (also used as external cron endpoint)
"""

from __future__ import annotations

import datetime as dt
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai_service
from app.collector import add_channel, collect_channel, collect_all_channels
from app.config import settings
from app.database import engine, get_session
from app.models import (
    AIAnalysis,
    Base,
    Channel,
    ChannelMetricsSnapshot,
    Post,
    PostMetricsSnapshot,
)
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


# ── App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="channel-radar",
    description="Live analytics dashboard for public Telegram channels",
    version="1.0.0",
    lifespan=lifespan,
)

import pathlib

_BASE_DIR = pathlib.Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=_BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_BASE_DIR / "templates")


# ── Template filters ──────────────────────────────────────────────────

def _format_number(value):
    """Format large numbers: 1234567 → '1.2M'."""
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def _time_ago(value):
    """Format datetime as 'X ago'."""
    if value is None:
        return "never"
    if isinstance(value, str):
        return value
    now = dt.datetime.now(dt.timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    diff = now - value
    if diff.days > 30:
        return f"{diff.days // 30}mo ago"
    if diff.days > 0:
        return f"{diff.days}d ago"
    hours = diff.seconds // 3600
    if hours > 0:
        return f"{hours}h ago"
    minutes = diff.seconds // 60
    return f"{minutes}m ago"


templates.env.filters["format_number"] = _format_number
templates.env.filters["time_ago"] = _time_ago


# ── Pages ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    """Main dashboard — list of all tracked channels."""
    result = await session.execute(
        select(Channel).order_by(Channel.added_at.desc())
    )
    channels = result.scalars().all()

    # Enrich with post counts
    channel_stats = []
    for ch in channels:
        count_result = await session.execute(
            select(func.count(Post.id)).where(Post.channel_username == ch.username)
        )
        post_count = count_result.scalar() or 0

        channel_stats.append({
            "channel": ch,
            "post_count": post_count,
        })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "channels": channel_stats,
        "ai_available": ai_service.is_ai_available(),
    })


@app.get("/channel/{username}", response_class=HTMLResponse)
async def channel_page(
    request: Request,
    username: str,
    period: str = Query("7d", regex="^(1d|7d|30d|all)$"),
    session: AsyncSession = Depends(get_session),
):
    """Channel detail page — metrics, posts, AI digest."""
    channel = await session.get(Channel, username.lower())
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    # ── Period filter ─────────────────────────────────────────
    now = dt.datetime.now(dt.timezone.utc)
    period_map = {
        "1d": now - dt.timedelta(days=1),
        "7d": now - dt.timedelta(days=7),
        "30d": now - dt.timedelta(days=30),
        "all": dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc),
    }
    since = period_map[period]

    # ── Posts ──────────────────────────────────────────────────
    result = await session.execute(
        select(Post)
        .where(Post.channel_username == username.lower())
        .where(Post.date >= since)
        .order_by(Post.date.desc())
    )
    posts = result.scalars().all()

    # ── Anomalies ─────────────────────────────────────────────
    posts_data = [
        {"message_id": p.message_id, "views": p.views or 0, "text": p.text}
        for p in posts
    ]
    anomalies = await ai_service.detect_anomalies(username, posts_data)
    anomaly_ids = {a["message_id"] for a in anomalies}

    # ── Subscriber history (for chart) ────────────────────────
    metrics_result = await session.execute(
        select(ChannelMetricsSnapshot)
        .where(ChannelMetricsSnapshot.channel_username == username.lower())
        .order_by(ChannelMetricsSnapshot.recorded_at.asc())
    )
    subscriber_history = [
        {
            "date": m.recorded_at.isoformat() if m.recorded_at else "",
            "subscribers": m.subscriber_count,
        }
        for m in metrics_result.scalars().all()
    ]

    # ── Views trend (aggregate by date) ───────────────────────
    views_by_date: dict[str, int] = {}
    for p in posts:
        if p.date:
            day_key = p.date.strftime("%Y-%m-%d")
            views_by_date[day_key] = views_by_date.get(day_key, 0) + (p.views or 0)

    views_trend = [
        {"date": k, "views": v}
        for k, v in sorted(views_by_date.items())
    ]

    # ── AI digest (cached) ────────────────────────────────────
    digest = None
    digest_result = await session.execute(
        select(AIAnalysis)
        .where(
            AIAnalysis.channel_username == username.lower(),
            AIAnalysis.analysis_type == "digest",
        )
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    )
    cached = digest_result.scalar_one_or_none()
    if cached:
        digest = cached.result

    return templates.TemplateResponse("channel.html", {
        "request": request,
        "channel": channel,
        "posts": posts,
        "period": period,
        "anomaly_ids": anomaly_ids,
        "anomalies": anomalies,
        "subscriber_history": subscriber_history,
        "views_trend": views_trend,
        "digest": digest,
        "ai_available": ai_service.is_ai_available(),
    })


@app.get("/post/{username}/{message_id}", response_class=HTMLResponse)
async def post_page(
    request: Request,
    username: str,
    message_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Post detail page — full text, metrics, history."""
    result = await session.execute(
        select(Post).where(
            Post.channel_username == username.lower(),
            Post.message_id == message_id,
        )
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    channel = await session.get(Channel, username.lower())

    # Metrics history for this post
    metrics_result = await session.execute(
        select(PostMetricsSnapshot)
        .where(PostMetricsSnapshot.post_id == post.id)
        .order_by(PostMetricsSnapshot.recorded_at.asc())
    )
    metrics_history = [
        {
            "date": m.recorded_at.isoformat() if m.recorded_at else "",
            "views": m.views or 0,
        }
        for m in metrics_result.scalars().all()
    ]

    return templates.TemplateResponse("post.html", {
        "request": request,
        "post": post,
        "channel": channel,
        "metrics_history": metrics_history,
    })


# ── API ───────────────────────────────────────────────────────────────

@app.post("/api/channels")
async def api_add_channel(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Add a channel by username. Called from the dashboard form."""
    body = await request.json()
    username = body.get("username", "").strip().lstrip("@").lower()

    if not username:
        return JSONResponse({"error": "Username is required"}, status_code=400)

    if len(username) > 128 or not username.replace("_", "").isalnum():
        return JSONResponse({"error": "Invalid username format"}, status_code=400)

    try:
        channel = await add_channel(session, username)
        await session.refresh(channel)
        return JSONResponse({
            "ok": True,
            "channel": {
                "username": channel.username,
                "title": channel.title or channel.username,
                "status": channel.status,
                "subscriber_count": channel.subscriber_count,
                "error_message": channel.error_message,
            },
        })
    except Exception as exc:
        logger.exception("Failed to add channel @%s", username)
        return JSONResponse(
            {"error": f"Failed to add channel: {exc}"},
            status_code=500,
        )


@app.get("/api/channels/{username}/digest")
async def api_channel_digest(
    username: str,
    session: AsyncSession = Depends(get_session),
):
    """Generate (or return cached) AI digest for a channel."""
    channel = await session.get(Channel, username.lower())
    if channel is None:
        raise HTTPException(status_code=404)

    # Get recent posts
    result = await session.execute(
        select(Post)
        .where(Post.channel_username == username.lower())
        .order_by(Post.date.desc())
        .limit(30)
    )
    posts = result.scalars().all()

    posts_data = [
        {
            "text": p.text,
            "date": p.date.isoformat() if p.date else "",
            "views": p.views or 0,
        }
        for p in posts
    ]

    digest = await ai_service.generate_channel_digest(username, posts_data)

    if digest is None:
        return JSONResponse({"digest": None, "error": "AI is unavailable or rate-limited"})

    # Cache the digest
    analysis = AIAnalysis(
        channel_username=username.lower(),
        analysis_type="digest",
        period_start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7),
        period_end=dt.datetime.now(dt.timezone.utc),
        result=digest,
        model_used="gemini-2.0-flash",
    )
    session.add(analysis)
    await session.commit()

    return JSONResponse({"digest": digest})


@app.get("/api/health")
async def health():
    """Health check — used by Render / monitoring."""
    return {"status": "ok", "ai_available": ai_service.is_ai_available()}


@app.get("/api/collect")
async def api_trigger_collect(session: AsyncSession = Depends(get_session)):
    """
    Trigger manual collection of all channels.

    Also used as the endpoint for external cron triggers
    (cron-job.org / GitHub Actions) to wake the service on free-tier
    hosting that sleeps during inactivity.
    """
    summary = await collect_all_channels(session)
    return JSONResponse({"ok": True, "summary": summary})
