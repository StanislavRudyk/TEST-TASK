# ADR-001: Hosting — Render.com (Free Tier)

## Status
Accepted

## Context
The service needs a free hosting platform that supports:
- Python web service (FastAPI + Uvicorn)
- PostgreSQL database
- Background periodic tasks (scheduled data collection)
- Public URL accessible at any time

## Considered Options

| Option | Pros | Cons |
|--------|------|------|
| **Render.com** | Free web + free Postgres (90 days), easy Docker deploy, built-in health checks | Service sleeps after 15min inactivity; cold start ~30s; Postgres expires after 90 days |
| Fly.io | Always-on free VM | Requires own Postgres setup or external DB; more complex config |
| Railway.app | Easy deploy, credit-based | Credit runs out; may stop mid-review |
| PythonAnywhere | Simple Flask/Django | Scheduled tasks limited on free tier; not great for async FastAPI |

## Decision
**Render.com** — best balance of simplicity, free Postgres, and straightforward deployment.

## Handling the "Sleep" Problem
Render free-tier services spin down after 15 minutes of inactivity. This creates two issues:

1. **Slow first request**: ~30 seconds cold start. Acceptable — documented in README.
2. **Background collection stops**: The APScheduler runs in-process, so it stops when the service sleeps.

**Solution**: Use an external cron trigger (e.g., [cron-job.org](https://cron-job.org) or GitHub Actions) that hits `GET /api/collect` every 30 minutes. This wakes the service AND triggers data collection. The APScheduler serves as a backup for when the service is already awake.

## Consequences
- First request after sleep takes ~30 seconds
- Free Postgres expires after 90 days (sufficient for evaluation)
- Need external cron to ensure regular collection
- Simple deployment via `render.yaml` blueprint
