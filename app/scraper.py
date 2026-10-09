

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_BASE = "https://t.me/s/"
_TIMEOUT = 20.0
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

@dataclass
class ScrapedPost:
    message_id: int
    text: str
    date: dt.datetime | None
    views: int
    reactions: dict[str, int]  
    media_type: str | None  
    url: str

@dataclass
class ScrapedChannel:
    username: str
    title: str
    description: str
    avatar_url: str | None
    subscriber_count: int | None
    posts: list[ScrapedPost] = field(default_factory=list)

async def scrape_channel(username: str) -> ScrapedChannel:
    """
    Fetch and parse t.me/s/<username>.

    Raises:
        ChannelNotFoundError  – 404 or page has no channel widget
        ChannelPrivateError   – page says the channel is private
        httpx.HTTPError       – network-level failures
    """
    username = _normalise_username(username)
    url = _BASE + username
    logger.info("Scraping %s", url)

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = await client.get(url)

    if resp.status_code == 404:
        raise ChannelNotFoundError(username)

    resp.raise_for_status()
    return parse_channel_page(username, resp.text)

def parse_channel_page(username: str, html: str) -> ScrapedChannel:
    """
    Pure function: HTML → ScrapedChannel.

    Testable without network (accepts raw HTML string).
    """
    soup = BeautifulSoup(html, "lxml")

    error_el = soup.select_one(".tgme_page_description")
    if error_el and "private" in (error_el.get_text() or "").lower():
        raise ChannelPrivateError(username)

    header = soup.select_one(".tgme_channel_info")
    if header is None:

        page_extra = soup.select_one(".tgme_page_extra")
        if page_extra is None:
            raise ChannelNotFoundError(username)

    title = _text(soup.select_one(".tgme_channel_info_header_title"))
    if not title:
        title = _text(soup.select_one(".tgme_page_title span"))
    description = _text(soup.select_one(".tgme_channel_info_description"))
    if not description:
        description = _text(soup.select_one(".tgme_page_description"))

    avatar_url = None
    avatar_el = soup.select_one(".tgme_page_photo_image img") or soup.select_one(
        ".tgme_channel_info_header_photo img"
    )
    if avatar_el:
        avatar_url = avatar_el.get("src")

    subscriber_count = _parse_subscriber_count(soup)

    posts: list[ScrapedPost] = []
    for widget in soup.select(".tgme_widget_message_wrap"):
        post = _parse_post(widget, username)
        if post is not None:
            posts.append(post)

    return ScrapedChannel(
        username=username,
        title=title or username,
        description=description or "",
        avatar_url=avatar_url,
        subscriber_count=subscriber_count,
        posts=posts,
    )

def _normalise_username(raw: str) -> str:
    """Strip @, whitespace, leading https://t.me/ etc."""
    raw = raw.strip().lstrip("@")

    for prefix in ("https://t.me/s/", "https://t.me/", "http://t.me/s/", "http://t.me/", "t.me/s/", "t.me/"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix):]
            break
    return raw.split("/")[0].split("?")[0].strip()

def _text(el: Tag | None) -> str:
    """Safe text extraction."""
    if el is None:
        return ""
    return el.get_text(separator=" ", strip=True)

def _parse_subscriber_count(soup: BeautifulSoup) -> int | None:
    """
    Extract subscriber count from e.g. '1.2M subscribers' or '12 345 subscribers'.
    """
    el = soup.select_one(".tgme_channel_info_counter .counter_value")
    if el is None:

        extra = soup.select_one(".tgme_page_extra")
        if extra:
            return _parse_count_text(extra.get_text())
        return None
    return _parse_count_text(el.get_text())

def _parse_count_text(text: str) -> int | None:
    """Parse '1.2M' / '12 345' / '500K' → int."""
    if not text:
        return None
    text = text.strip().lower().replace("\xa0", "").replace(" ", "")

    text = re.sub(r"[a-zа-яіїєґ]+", lambda m: m.group() if m.group() in ("k", "m", "b") else "", text)
    text = text.strip()
    if not text:
        return None
    multiplier = 1
    if text.endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith("b"):
        multiplier = 1_000_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None

def _parse_post(wrap: Tag, channel_username: str) -> ScrapedPost | None:
    """Parse a single .tgme_widget_message_wrap → ScrapedPost or None."""
    msg = wrap.select_one(".tgme_widget_message")
    if msg is None:
        return None

    data_post = msg.get("data-post", "")
    if "/" in str(data_post):
        try:
            message_id = int(str(data_post).split("/")[-1])
        except ValueError:
            return None
    else:
        return None

    text_el = msg.select_one(".tgme_widget_message_text")
    text = _text(text_el) if text_el else ""

    date = None
    time_el = msg.select_one("time")
    if time_el:
        raw_dt = time_el.get("datetime")
        if raw_dt:
            try:
                date = dt.datetime.fromisoformat(str(raw_dt).replace("Z", "+00:00"))
            except ValueError:
                pass

    views = 0
    views_el = msg.select_one(".tgme_widget_message_views")
    if views_el:
        views = _parse_count_text(views_el.get_text()) or 0

    reactions: dict[str, int] = {}
    for reaction_el in msg.select(".tgme_widget_message_reaction"):
        emoji_el = reaction_el.select_one(".tgme_widget_message_reaction_emoji, .emoji")
        count_el = reaction_el.select_one(".tgme_widget_message_reaction_count")
        if emoji_el and count_el:
            emoji = emoji_el.get_text(strip=True)
            count = _parse_count_text(count_el.get_text()) or 0
            if emoji:
                reactions[emoji] = count

    media_type = None
    if msg.select_one(".tgme_widget_message_photo"):
        media_type = "photo"
    elif msg.select_one(".tgme_widget_message_video"):
        media_type = "video"
    elif msg.select_one(".tgme_widget_message_document"):
        media_type = "document"

    url = f"https://t.me/{channel_username}/{message_id}"

    return ScrapedPost(
        message_id=message_id,
        text=text,
        date=date,
        views=views,
        reactions=reactions,
        media_type=media_type,
        url=url,
    )

class ChannelNotFoundError(Exception):
    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"Channel @{username} not found")

class ChannelPrivateError(Exception):
    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"Channel @{username} is private")
