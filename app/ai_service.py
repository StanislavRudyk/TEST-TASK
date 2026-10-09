

from __future__ import annotations

import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

_model = None

def _get_model():
#ленивую инициализацию модели Gemini. 
    global _model
    if _model is not None:
        return _model
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY is not set — AI features disabled")
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel("gemini-3.8-flash")
        logger.info("Gemini model initialised (gemini-3.8-flash)")
        return _model
    except Exception:
        logger.exception("Failed to initialise Gemini model")
        return None

async def generate_channel_digest(
    channel_name: str,
    posts: list[dict],
    period_label: str = "last 7 days",
) -> str | None:
#Сводка публикаций канала.
# `posts`  список словарей с ключами: text, date, views.
#Возвращает строку в формате Markdown или None, если данные недоступны.
    model = _get_model()
    if model is None:
        return None

    if not posts:
        return "No posts in the selected period."

    post_lines = []
    for i, p in enumerate(posts[:30]):  
        date_str = p.get("date", "")
        views = p.get("views", 0)
        text = (p.get("text") or "")[:300]  
        post_lines.append(f"{i+1}. [{date_str}] (views: {views}) {text}")

    posts_block = "\n".join(post_lines)

    prompt = f"""You are an analytics assistant. Summarise the Telegram channel @{channel_name} activity for {period_label}.

Posts:
{posts_block}

Write a concise digest (3-5 bullet points) covering:
- Main topics discussed
- Most notable/popular posts
- Overall posting frequency and engagement trends

Keep it factual and concise. Write in the same language as the posts.
If posts are in multiple languages, use English.
"""

    return await _safe_generate(prompt)

async def categorise_post(text: str) -> str | None:
#Присвойение  отдельной публикации краткую метку категории или темы.
    model = _get_model()
    if model is None:
        return None

    if not text or len(text.strip()) < 10:
        return None

    prompt = f"""Assign a single short topic/category label (1-3 words) to this Telegram post.
Examples of labels: "Tech News", "Politics", "Crypto", "Meme", "Tutorial", "Announcement", "Personal".

Post text:
{text[:500]}

Reply with ONLY the label, nothing else."""

    return await _safe_generate(prompt)

async def detect_anomalies(
    channel_name: str,
    posts_with_stats: list[dict],
) -> list[dict]:
#публикации, показатели вовлеченности которых значительно превышают средние значения по каналу.
#Возвращает список словарей: {message_id, reason}.
#Простая эвристика (LLM не требуется): количество просмотров > 2 × среднее значение.
    if len(posts_with_stats) < 3:
        return []

    views_list = [p.get("views", 0) for p in posts_with_stats if p.get("views")]
    if not views_list:
        return []

    avg_views = sum(views_list) / len(views_list)
    threshold = avg_views * 2

    anomalies = []
    for p in posts_with_stats:
        v = p.get("views", 0)
        if v > threshold and avg_views > 0:
            ratio = round(v / avg_views, 1)
            anomalies.append({
                "message_id": p.get("message_id"),
                "views": v,
                "avg_views": round(avg_views),
                "reason": f"Views {v:,} is {ratio}× above channel average ({round(avg_views):,})",
            })

    return anomalies

async def _safe_generate(prompt: str) -> str | None:
#Вызывает Gemini с полной обработкой ошибок. 
    model = _get_model()
    if model is None:
        return None
    try:
        response = await model.generate_content_async(prompt)
        if response and response.text:
            return response.text.strip()
        return None
    except Exception as exc:

        logger.warning("LLM call failed: %s", exc)
        return None

def is_ai_available() -> bool:
#Быстрая проверка панели управления, чтобы узнать, активны ли функции ИИ.
    return _get_model() is not None
