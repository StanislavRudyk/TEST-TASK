

import datetime as dt

import pytest

from app.scraper import (
    ChannelNotFoundError,
    ChannelPrivateError,
    parse_channel_page,
    _normalise_username,
    _parse_count_text,
)

class TestParseChannel:
    def test_extracts_title(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        assert result.title == "Durov's Channel"

    def test_extracts_description(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        assert "Pavel Durov" in result.description

    def test_extracts_subscriber_count(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        assert result.subscriber_count == 1_200_000

    def test_username_preserved(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        assert result.username == "durov"

class TestParsePosts:
    def test_extracts_correct_number_of_posts(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        assert len(result.posts) == 3

    def test_post_message_id(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        ids = [p.message_id for p in result.posts]
        assert 123 in ids
        assert 124 in ids
        assert 125 in ids

    def test_post_text(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        post = next(p for p in result.posts if p.message_id == 123)
        assert "Hello world" in post.text

    def test_post_date(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        post = next(p for p in result.posts if p.message_id == 123)
        assert post.date is not None
        assert post.date.year == 2025
        assert post.date.month == 1
        assert post.date.day == 15

    def test_post_views(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        post = next(p for p in result.posts if p.message_id == 123)
        assert post.views == 45_200

    def test_post_reactions(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        post = next(p for p in result.posts if p.message_id == 123)
        assert "👍" in post.reactions
        assert post.reactions["👍"] == 1200
        assert "❤️" in post.reactions
        assert post.reactions["❤️"] == 350

    def test_post_media_type_photo(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        post = next(p for p in result.posts if p.message_id == 123)
        assert post.media_type == "photo"

    def test_post_media_type_video(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        post = next(p for p in result.posts if p.message_id == 125)
        assert post.media_type == "video"

    def test_post_no_media(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        post = next(p for p in result.posts if p.message_id == 124)
        assert post.media_type is None

    def test_post_url(self, sample_channel_html):
        result = parse_channel_page("durov", sample_channel_html)
        post = next(p for p in result.posts if p.message_id == 123)
        assert post.url == "https://t.me/durov/123"

class TestParseCountText:
    @pytest.mark.parametrize("text,expected", [
        ("1.2K", 1200),
        ("1.2M", 1_200_000),
        ("45.2K", 45_200),
        ("500", 500),
        ("1 234", 1234),
        ("1B", 1_000_000_000),
        ("0", 0),
        ("", None),
        ("abc", None),
    ])
    def test_parse_count_text(self, text, expected):
        assert _parse_count_text(text) == expected

class TestNormaliseUsername:
    @pytest.mark.parametrize("raw,expected", [
        ("durov", "durov"),
        ("@durov", "durov"),
        ("  @durov  ", "durov"),
        ("https://t.me/durov", "durov"),
        ("https://t.me/s/durov", "durov"),
        ("t.me/durov", "durov"),
        ("t.me/s/durov", "durov"),
        ("DUROV", "DUROV"),
    ])
    def test_normalise(self, raw, expected):
        assert _normalise_username(raw) == expected

class TestErrorCases:
    def test_private_channel_raises(self, private_channel_html):
        with pytest.raises(ChannelPrivateError):
            parse_channel_page("private_chan", private_channel_html)

    def test_not_found_raises(self, not_found_html):
        with pytest.raises(ChannelNotFoundError):
            parse_channel_page("no_such_chan", not_found_html)
