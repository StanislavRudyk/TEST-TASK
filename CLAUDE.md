# CLAUDE.md — Project Conventions for AI Agents

## Architecture

channel-radar is a **monolith** — single FastAPI process that handles HTTP requests,
background scheduling, scraping, and AI calls. No microservices, no queues.

```
app/
├── main.py          — FastAPI app, routes, template rendering
├── config.py        — pydantic-settings, reads from .env
├── database.py      — SQLAlchemy async engine + session factory
├── models.py        — ORM models (Channel, Post, *MetricsSnapshot, AIAnalysis)
├── scraper.py       — HTTP fetch + HTML parser for t.me/s/<channel>
├── collector.py     — orchestrates scrape → DB upsert → AI processing
├── ai_service.py    — Gemini wrapper with graceful degradation
├── scheduler.py     — APScheduler for periodic collection
├── templates/       — Jinja2 HTML templates
└── static/          — CSS + JS
```

## Layer Boundaries

| Layer | Responsibility | Depends On |
|-------|---------------|------------|
| `main.py` (routes) | HTTP, templates, request validation | collector, ai_service, models |
| `collector.py` | Orchestration: scrape → upsert → AI | scraper, models, ai_service |
| `scraper.py` | HTTP fetch + HTML parsing | httpx, beautifulsoup4 (no DB) |
| `ai_service.py` | LLM calls with error wrapping | google-generativeai, config |
| `models.py` | ORM schema | sqlalchemy |
| `scheduler.py` | Cron-like periodic triggers | collector |

**Rule**: `scraper.py` must never import DB/ORM models. It returns pure dataclasses.
This keeps it testable without a database.

## Key Conventions

### Natural Keys
- Channel PK = `username` (string), not auto-increment integer
- Post uniqueness = `(channel_username, message_id)` constraint
- This makes upserts idempotent: `INSERT ... ON CONFLICT DO UPDATE`

### Metrics History
- Current values live on `channels.subscriber_count` and `posts.views`
- Historical snapshots are appended to `channel_metrics_history` / `post_metrics_history`
- Never delete snapshots; they're append-only

### AI Graceful Degradation
- Every AI function returns `None` on failure
- Dashboard renders without AI data (shows placeholders)
- Never `raise` from AI code in production flow

### Error Handling in Collector
- Channel errors set `status='error'` + `error_message` on the Channel row
- Collection continues for other channels even if one fails
- AI processing failures are logged but never block the scrape

## Testing Rules
- **No network in tests** — parser tests use HTML fixtures from `tests/fixtures/`
- **AI is mocked** — `ai_service._model` is patched to a mock or `None`
- **No real DB** — idempotency tests verify parser output stability

## Environment Variables
See `.env.example`. Critical ones:
- `DATABASE_URL` — PostgreSQL connection string (asyncpg prefix)
- `GEMINI_API_KEY` — Google AI Studio key (empty = AI disabled)
- `COLLECT_INTERVAL_MINUTES` — scheduler interval (default: 30)

## Deployment
- Render.com via `render.yaml` blueprint
- External cron hits `GET /api/collect` to wake the service and trigger collection
- Tables are auto-created on startup via `Base.metadata.create_all`
