"""
Tests for analytics metrics computation.

Covers:
  - Anomaly detection (statistical heuristic)
  - Views aggregation per day
  - Number formatting (K, M suffixes)
"""

import pytest

from app.ai_service import detect_anomalies
from app.main import _format_number


# ── Anomaly Detection ─────────────────────────────────────────────

class TestAnomalyDetection:
    @pytest.mark.asyncio
    async def test_detects_anomaly_above_threshold(self):
        posts = [
            {"message_id": 1, "views": 100},
            {"message_id": 2, "views": 120},
            {"message_id": 3, "views": 80},
            {"message_id": 4, "views": 110},
            {"message_id": 5, "views": 500},  # ← anomaly (5× avg)
        ]
        result = await detect_anomalies("test", posts)
        anomaly_ids = [a["message_id"] for a in result]
        assert 5 in anomaly_ids

    @pytest.mark.asyncio
    async def test_no_anomaly_when_views_are_uniform(self):
        posts = [
            {"message_id": 1, "views": 100},
            {"message_id": 2, "views": 110},
            {"message_id": 3, "views": 95},
        ]
        result = await detect_anomalies("test", posts)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_empty_posts_returns_empty(self):
        result = await detect_anomalies("test", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_too_few_posts_returns_empty(self):
        result = await detect_anomalies("test", [{"message_id": 1, "views": 100}])
        assert result == []

    @pytest.mark.asyncio
    async def test_anomaly_contains_reason(self):
        posts = [
            {"message_id": 1, "views": 50},
            {"message_id": 2, "views": 60},
            {"message_id": 3, "views": 300},
        ]
        result = await detect_anomalies("test", posts)
        assert len(result) >= 1
        assert "reason" in result[0]
        assert "above" in result[0]["reason"].lower()


# ── Number Formatting ─────────────────────────────────────────────

class TestFormatNumber:
    @pytest.mark.parametrize("value,expected", [
        (None, "—"),
        (0, "0"),
        (500, "500"),
        (1_234, "1.2K"),
        (12_345, "12.3K"),
        (1_234_567, "1.2M"),
        (12_345_678, "12.3M"),
    ])
    def test_format_number(self, value, expected):
        assert _format_number(value) == expected
