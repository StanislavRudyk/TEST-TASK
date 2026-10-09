# ADR-003: LLM Provider — Google Gemini (Free Tier)

## Status
Accepted

## Context
The AI layer needs a free LLM for:
1. Channel digest / weekly summary
2. Post topic categorisation
3. (Anomaly detection uses a statistical heuristic, no LLM needed)

## Considered Options

| Option | Free Tier | Pros | Cons |
|--------|-----------|------|------|
| **Google AI Studio (Gemini)** | 15 RPM on gemini-2.0-flash | No credit card needed; generous free quota; fast | Google ecosystem |
| OpenRouter (free models) | Varies by model | Multiple models | Less predictable availability |
| Groq (free tier) | 30 RPM on some models | Very fast inference | Limited model selection |

## Decision
**Google AI Studio** with `gemini-2.0-flash`.

### Why
- Free key without credit card (via aistudio.google.com/apikey)
- `gemini-2.0-flash` is fast and capable enough for categorisation/summarisation
- 15 RPM free tier is sufficient for a dashboard serving ~10 channels

## Graceful Degradation
The AI layer is designed to **never crash the dashboard**:

```python
async def _safe_generate(prompt: str) -> str | None:
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception:
        logger.warning("LLM call failed")
        return None  # ← dashboard continues without AI
```

- All AI functions return `None` on failure
- Dashboard shows "AI unavailable" placeholder
- Anomaly detection works without LLM (statistical heuristic)
- AI processing during collection is wrapped in try/except and never blocks the scrape

## Rate Limit Handling
- Post categorisation is limited to 10 posts per collection run
- Digest generation is on-demand (user clicks button), not automatic
- Results are cached in `ai_analyses` table to avoid redundant calls

## Consequences
- If Google AI Studio is down or rate-limited, AI sections show placeholders
- Dashboard functionality is 100% intact without AI
- Need `.env` with `GEMINI_API_KEY` for AI features to work
