

import pathlib

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_channel_html() -> str:
    """Full HTML of a normal public channel page."""
    return (FIXTURES_DIR / "sample_channel_page.html").read_text(encoding="utf-8")

@pytest.fixture
def private_channel_html() -> str:
    """HTML of a private channel page."""
    return (FIXTURES_DIR / "private_channel_page.html").read_text(encoding="utf-8")

@pytest.fixture
def not_found_html() -> str:
    """HTML of a non-existent channel page."""
    return (FIXTURES_DIR / "not_found_page.html").read_text(encoding="utf-8")
