"""Shared pytest fixtures for backend API isolation."""

from collections.abc import Iterator

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_api_cache_between_tests() -> Iterator[None]:
    """Keep persistent throttle counters from leaking across test boundaries."""
    cache.clear()
    yield
    cache.clear()
