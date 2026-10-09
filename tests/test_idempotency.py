"""
Tests for idempotent post upsert logic.

Verifies that re-inserting the same post (same channel + message_id)
updates views/reactions without creating duplicates.

These tests use an in-memory approach — we test the data structures and
logic, not the actual DB (which would require a running Postgres).
"""

import datetime as dt

import pytest

from app.scraper import ScrapedPost, ScrapedChannel, parse_channel_page


class TestIdempotency:
    """
    Verify that parsing the same HTML twice produces identical results
    (same message_ids, same count), which is the precondition for
    DB-level idempotency via ON CONFLICT.
    """

    def test_same_html_produces_same_posts(self, sample_channel_html):
        r1 = parse_channel_page("durov", sample_channel_html)
        r2 = parse_channel_page("durov", sample_channel_html)

        assert len(r1.posts) == len(r2.posts)

        ids1 = sorted(p.message_id for p in r1.posts)
        ids2 = sorted(p.message_id for p in r2.posts)
        assert ids1 == ids2

    def test_no_duplicate_message_ids(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        ids = [p.message_id for p in result.posts]
        assert len(ids) == len(set(ids)), "Duplicate message_ids detected!"

    def test_post_natural_key_is_deterministic(self, sample_channel_html):
        """The (channel_username, message_id) pair is stable across parses."""
        r1 = parse_channel_page("durov", sample_channel_html)
        r2 = parse_channel_page("durov", sample_channel_html)

        for p1, p2 in zip(
            sorted(r1.posts, key=lambda p: p.message_id),
            sorted(r2.posts, key=lambda p: p.message_id),
        ):
            assert p1.message_id == p2.message_id
            assert p1.text == p2.text

    def test_views_can_change_between_scrapes(self):
        """
        Simulates two scrapes where views differ — the parser should
        return the new value (DB upsert will update it).
        """
        html_v1 = """
        <div class="tgme_channel_info">
            <div class="tgme_channel_info_header_title">Test</div>
        </div>
        <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message" data-post="test/1">
                <div class="tgme_widget_message_text">Post 1</div>
                <time datetime="2025-01-01T00:00:00+00:00"></time>
                <span class="tgme_widget_message_views">100</span>
            </div>
        </div>
        """
        html_v2 = html_v1.replace("100", "250")

        r1 = parse_channel_page("test", html_v1)
        r2 = parse_channel_page("test", html_v2)

        assert r1.posts[0].message_id == r2.posts[0].message_id
        assert r1.posts[0].views == 100
        assert r2.posts[0].views == 250
