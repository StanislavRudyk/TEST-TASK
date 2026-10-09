# ADR-002: Metrics Storage — Snapshot History Tables

## Status
Accepted

## Context
Telegram post views and channel subscribers change over time. The task requires storing
this dynamic, not just the latest value.

## Considered Options

| Option | Pros | Cons |
|--------|------|------|
| **Separate history tables** | Clean separation; query flexibility; no bloat on main tables | Extra joins for "current" value; more rows over time |
| JSONB array on post row | Single table; simple schema | Unbounded growth in a single cell; hard to query/aggregate |
| Temporal/bi-temporal table | Full audit trail | Over-engineered for this scale |
| Only store latest | Simple | Loses historical data (violates requirement) |

## Decision
**Separate snapshot tables**: `post_metrics_history` and `channel_metrics_history`.

### Schema
```
post_metrics_history
├── id (PK, auto)
├── post_id (FK → posts.id)
├── views
├── reactions (JSONB)
└── recorded_at (timestamptz, default now())

channel_metrics_history
├── id (PK, auto)
├── channel_username (FK → channels.username)
├── subscriber_count
└── recorded_at (timestamptz, default now())
```

### Why
- Each collection run appends one row per post and one row per channel.
- Charts can query history with a simple `ORDER BY recorded_at`.
- "Current" value is always on the main `posts` / `channels` table (updated on each scrape).
- History is append-only — no risk of losing data on upsert.

## Consequences
- Tables grow with number of channels × collection frequency. For 10 channels collected
  every 30 minutes with ~20 posts each: ~400 post snapshots/hour, ~10 channel snapshots/hour.
  Well within free-tier Postgres limits for months.
- Indexes on `(post_id, recorded_at)` and `(channel_username, recorded_at)` ensure efficient
  time-range queries.
