

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app import ai_service

class TestAIGracefulDegradation:
    """AI layer must never crash the app, even when LLM is down."""

    def test_is_ai_available_without_key(self):
        with patch.object(ai_service, "_model", None):
            with patch.object(ai_service.settings, "gemini_api_key", ""):

                ai_service._model = None
                result = ai_service.is_ai_available()
                assert result is False

    @pytest.mark.asyncio
    async def test_digest_returns_none_without_key(self):
        ai_service._model = None
        with patch.object(ai_service.settings, "gemini_api_key", ""):
            result = await ai_service.generate_channel_digest("test", [])
            assert result is None or result == "No posts in the selected period."

    @pytest.mark.asyncio
    async def test_categorise_returns_none_without_key(self):
        ai_service._model = None
        with patch.object(ai_service.settings, "gemini_api_key", ""):
            result = await ai_service.categorise_post("some text here to test")
            assert result is None

    @pytest.mark.asyncio
    async def test_safe_generate_catches_exceptions(self):
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(side_effect=Exception("API error"))
        ai_service._model = mock_model

        result = await ai_service._safe_generate("test prompt")
        assert result is None

        ai_service._model = None

    @pytest.mark.asyncio
    async def test_digest_with_mocked_model(self):
        """Simulate a working LLM returning a digest."""
        mock_response = MagicMock()
        mock_response.text = "• Topic 1\n• Topic 2\n• Topic 3"

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        ai_service._model = mock_model

        posts = [
            {"text": "Hello world", "date": "2025-01-01", "views": 100},
            {"text": "Another post", "date": "2025-01-02", "views": 200},
        ]
        result = await ai_service.generate_channel_digest("test", posts)
        assert result is not None
        assert "Topic" in result

        ai_service._model = None

    @pytest.mark.asyncio
    async def test_categorise_with_mocked_model(self):
        """Simulate a working LLM returning a category."""
        mock_response = MagicMock()
        mock_response.text = "Tech News"

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        ai_service._model = mock_model

        result = await ai_service.categorise_post(
            "Breaking: new smartphone released with revolutionary features"
        )
        assert result == "Tech News"

        ai_service._model = None
