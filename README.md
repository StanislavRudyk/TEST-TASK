# channel-radar 📡

> Live analytics dashboard for public Telegram channels.

**🔗 Live service**: `<YOUR_RENDER_URL>` _(replace after deploy)_

---

## What It Does

1. **Scrapes** public Telegram channels via web preview (`t.me/s/<channel>`) — no Bot API, no tokens
2. **Stores** posts, views, reactions, and subscriber counts in PostgreSQL, tracking changes over time
3. **Analyses** content via Google Gemini (free tier) — channel digests, post categorisation, anomaly detection
4. **Shows** everything in a live dashboard you can open in a browser anytime

## Quick Start (Local)

```bash
# 1. Clone & install
git clone <repo-url> && cd channel-radar
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env: set DATABASE_URL (PostgreSQL) and optionally GEMINI_API_KEY

# 3. Run
uvicorn app.main:app --reload

# Open http://localhost:8000
```

**Requirements**: Python 3.11+, PostgreSQL (local or cloud).

For local Postgres, you can use Docker:
```bash
docker run -d --name radar-pg -e POSTGRES_DB=channel_radar -e POSTGRES_PASSWORD=pass -p 5432:5432 postgres:16
# DATABASE_URL=postgresql+asyncpg://postgres:pass@localhost:5432/channel_radar
```

## How to Use

1. Open the dashboard
2. Type a channel username (e.g. `@durov`) in the input field
3. Click **Add Channel**
4. Within seconds, the channel appears with its posts and metrics
5. Click on a channel to see trends, AI digest, posts, and anomalies
6. Click on a post to see its detail page with metrics history

## Data Model

```
channels (PK: username)
├── title, description, avatar_url
├── subscriber_count (current)
├── status: pending | collecting | active | error
├── last_collected_at
│
├── posts (UK: channel_username + message_id)
│   ├── text, date, views, reactions (JSONB)
│   ├── media_type, url
│   ├── ai_category, ai_summary, is_anomaly
│   └── post_metrics_history (append-only snapshots)
│       └── views, reactions, recorded_at
│
├── channel_metrics_history (append-only)
│   └── subscriber_count, recorded_at
│
└── ai_analyses (cached LLM results)
    └── analysis_type, period, result
```

### Why This Schema

- **Natural key** (`username` for channels, `channel_username + message_id` for posts) — makes upserts idempotent. Re-scraping never creates duplicates.
- **Separate history tables** for metrics — views and subscribers change over time. Each collection appends a snapshot row. The "current" value stays on the main table for fast reads.
- **JSONB for reactions** — Telegram reactions are dynamic (emoji set changes), so fixed columns would break. JSONB handles any structure.

## AI Layer

Uses **Google Gemini** (`gemini-2.0-flash`) via free tier from [AI Studio](https://aistudio.google.com/apikey).

### Features
| Feature | How It Works | LLM Required? |
|---------|-------------|---------------|
| Channel digest | Summarises recent posts (3-5 bullets) | ✅ Yes |
| Post categorisation | Assigns topic label (e.g. "Tech News") | ✅ Yes |
| Anomaly detection | Flags posts with views > 2× channel average | ❌ No (statistical) |

### Graceful Degradation
If Gemini is unavailable (no key, rate-limited, or API error):
- Dashboard continues working normally
- AI sections show "unavailable" placeholder
- Anomaly detection (statistical) still works
- No crashes, no error pages

### Rate Limits
- Post categorisation: max 10 posts per collection run
- Digest: generated on-demand (user clicks button), cached in DB
- All calls wrapped in try/except → return `None` on failure

## Deployment

### Render.com (Free Tier)

```bash
# Option 1: One-click via render.yaml
# Push to GitHub, connect repo on Render, deploy

# Option 2: Manual
# Create Web Service (Docker) + PostgreSQL database
# Set env vars: DATABASE_URL (from Render DB), GEMINI_API_KEY
```

### Handling the Sleep Problem

Render free tier sleeps after 15 min of inactivity.

**Impact**: First request after sleep takes ~30 seconds. Background collection stops.

**Solution**: External cron trigger (e.g., [cron-job.org](https://cron-job.org)) hits `GET /api/collect` every 30 minutes. This:
1. Wakes the service
2. Triggers data collection for all channels
3. Returns summary of what was collected

The in-process APScheduler serves as a backup when the service is already awake.

### Limitations
- Free Postgres on Render expires after 90 days
- Cold start ~30 seconds
- Service may be slow on first load after inactivity

## Tests

```bash
# Run all tests (no network, no DB, AI mocked)
pytest -v

# With coverage
pytest --cov=app --cov-report=term-missing
```

### What's Tested
| Test File | Covers | Network? |
|-----------|--------|----------|
| `test_scraper.py` | HTML parsing, metadata, posts, reactions, edge cases | ❌ No (fixtures) |
| `test_idempotency.py` | Natural key stability, no duplicates, views updates | ❌ No |
| `test_metrics.py` | Anomaly detection, number formatting | ❌ No |
| `test_ai_service.py` | Graceful degradation, mocked LLM calls | ❌ No (mocked) |

## What's NOT Implemented (and Why)

- **Authentication** — not required by spec, service is public
- **Kubernetes / microservices** — explicitly excluded by spec
- **Celery / RabbitMQ** — APScheduler + cron trigger is sufficient for this scale
- **Hundreds of channels** — designed for ~10, as per spec
- **100% test coverage** — tests cover the risky parts (parsing, idempotency, AI degradation)
- **Beautiful UI** — clean and functional, not a design showcase (per spec: "акуратний і зрозумілий вистачає")

## Project Structure

```
channel-radar/
├── app/
│   ├── main.py            # FastAPI routes + app
│   ├── config.py          # Settings from .env
│   ├── database.py        # Async SQLAlchemy engine
│   ├── models.py          # ORM models
│   ├── scraper.py         # t.me/s/ parser
│   ├── collector.py       # Scrape → DB orchestration
│   ├── ai_service.py      # Gemini with graceful degradation
│   ├── scheduler.py       # APScheduler background tasks
│   ├── templates/         # Jinja2 HTML
│   └── static/            # CSS + JS
├── tests/
│   ├── fixtures/          # HTML fixtures for parser tests
│   ├── test_scraper.py
│   ├── test_idempotency.py
│   ├── test_metrics.py
│   └── test_ai_service.py
├── docs/adr/
│   ├── 001-hosting.md
│   ├── 002-metrics-storage.md
│   └── 003-llm-provider.md
├── CLAUDE.md              # Agent conventions
├── .env.example
├── Dockerfile
├── render.yaml
└── requirements.txt
```
