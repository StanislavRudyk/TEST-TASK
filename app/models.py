

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Channel(Base):
    """A tracked Telegram channel.  PK = username (natural key)."""

    __tablename__ = "channels"

    username: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    subscriber_count: Mapped[int | None] = mapped_column(BigInteger)

    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)

    added_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_collected_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    posts: Mapped[list[Post]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    metrics_history: Mapped[list[ChannelMetricsSnapshot]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    ai_analyses: Mapped[list[AIAnalysis]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )

class Post(Base):
    """
    A single post from a Telegram channel.

    Natural key = (channel_username, message_id).
    message_id is the numeric Telegram ID visible in t.me/s/ URLs.
    """

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_username: Mapped[str] = mapped_column(
        String(128), ForeignKey("channels.username", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    text: Mapped[str | None] = mapped_column(Text)
    date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    views: Mapped[int | None] = mapped_column(BigInteger, default=0)
    reactions: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    media_type: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(512))

    ai_category: Mapped[str | None] = mapped_column(String(128))
    ai_summary: Mapped[str | None] = mapped_column(Text)
    is_anomaly: Mapped[bool | None] = mapped_column(default=False)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("channel_username", "message_id", name="uq_post_natural_key"),
        Index("ix_posts_channel_date", "channel_username", "date"),
    )

    channel: Mapped[Channel] = relationship(back_populates="posts")
    metrics_history: Mapped[list[PostMetricsSnapshot]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )

class ChannelMetricsSnapshot(Base):
    """Point-in-time snapshot of channel-level metrics (subscribers)."""

    __tablename__ = "channel_metrics_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_username: Mapped[str] = mapped_column(
        String(128), ForeignKey("channels.username", ondelete="CASCADE"), nullable=False
    )
    subscriber_count: Mapped[int | None] = mapped_column(BigInteger)
    recorded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_ch_metrics_channel_time", "channel_username", "recorded_at"),
    )

    channel: Mapped[Channel] = relationship(back_populates="metrics_history")

class PostMetricsSnapshot(Base):
    """Point-in-time snapshot of post-level metrics (views, reactions)."""

    __tablename__ = "post_metrics_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    views: Mapped[int | None] = mapped_column(BigInteger, default=0)
    reactions: Mapped[dict | None] = mapped_column(JSONB)
    recorded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_post_metrics_post_time", "post_id", "recorded_at"),
    )

    post: Mapped[Post] = relationship(back_populates="metrics_history")

class AIAnalysis(Base):
    """
    Cached result of an LLM analysis.

    analysis_type: 'digest' | 'anomaly_report' | etc.
    """

    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_username: Mapped[str] = mapped_column(
        String(128), ForeignKey("channels.username", ondelete="CASCADE"), nullable=False
    )
    analysis_type: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_ai_channel_type", "channel_username", "analysis_type"),
    )

    channel: Mapped[Channel] = relationship(back_populates="ai_analyses")
