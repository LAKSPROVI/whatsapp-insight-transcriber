"""
Testes para o serviço de cache (cache_service).
"""
import os

# Configurar variáveis ANTES de importar módulos da app
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-fake-12345")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-only")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "TestAdmin123")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import app.services.cache_service as cache_mod
from app.services.cache_service import (
    make_cache_key,
    get_cached_result,
    set_cached_result,
    invalidate_cache,
    get_cache_stats,
    cached,
    close_redis,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_cache_globals():
    """Reset module-level globals before each test."""
    cache_mod._redis_client = None
    cache_mod._redis_available = None
    cache_mod._stats.update({"hits": 0, "misses": 0, "errors": 0, "sets": 0})
    yield
    cache_mod._redis_client = None
    cache_mod._redis_available = None


# ─── make_cache_key ──────────────────────────────────────────────────────────

class TestMakeCacheKey:
    def test_consistent_keys_for_same_content(self):
        """Same content always produces the same key."""
        key1 = make_cache_key("hello world")
        key2 = make_cache_key("hello world")
        assert key1 == key2

    def test_different_content_different_keys(self):
        """Different content produces different keys."""
        key1 = make_cache_key("hello world")
        key2 = make_cache_key("goodbye world")
        assert key1 != key2

    def test_custom_prefix(self):
        """Custom prefix is included in the key."""
        key = make_cache_key("content", prefix="myprefix")
        assert key.startswith("myprefix:")

    def test_key_format_prefix_colon_hash(self):
        """Key format is 'prefix:hash'."""
        key = make_cache_key("test", prefix="pfx")
        parts = key.split(":")
        assert len(parts) == 2
        assert parts[0] == "pfx"
        # SHA256 hex digest is 64 chars
        assert len(parts[1]) == 64

    def test_default_prefix_is_wit(self):
        """Default prefix is 'wit'."""
        key = make_cache_key("something")
        assert key.startswith("wit:")


# ─── Cache without Redis ─────────────────────────────────────────────────────

class TestCacheWithoutRedis:
    """All tests run with CACHE_ENABLED=false so Redis is never available."""

    @pytest.mark.asyncio
    async def test_get_cached_result_returns_none(self):
        result = await get_cached_result("any:key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_cached_result_returns_false(self):
        result = await set_cached_result("any:key", {"data": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_cache_returns_false(self):
        result = await invalidate_cache("any:key")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_cache_stats_returns_dict(self):
        stats = await get_cache_stats()
        assert isinstance(stats, dict)
        assert "hits" in stats
        assert "misses" in stats
        assert "sets" in stats
        assert "errors" in stats
        assert "hit_rate" in stats
        assert stats["redis_connected"] is False

    @pytest.mark.asyncio
    async def test_stats_track_misses(self):
        """get_cached_result increments misses when Redis is unavailable."""
        await get_cached_result("key1")
        await get_cached_result("key2")
        assert cache_mod._stats["misses"] == 2

    @pytest.mark.asyncio
    async def test_stats_hit_rate_zero_without_redis(self):
        await get_cached_result("k")
        stats = await get_cache_stats()
        # One miss from the get above, one more from get_cache_stats calling _get_redis
        assert stats["hit_rate"] == 0.0


# ─── cached decorator ────────────────────────────────────────────────────────

class TestCachedDecorator:
    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self):
        """Decorated function keeps original name and docstring."""

        @cached(ttl=60, prefix="test")
        async def my_function(text: str) -> dict:
            """My docstring."""
            return {"result": text}

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    @pytest.mark.asyncio
    async def test_function_called_when_no_cache(self):
        """With Redis unavailable, the underlying function is always called."""
        call_count = 0

        @cached(ttl=60, prefix="test")
        async def compute(text: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"value": text}

        # String must be > 10 chars to be treated as cacheable content
        result = await compute("this is a long enough string for caching")
        assert result == {"value": "this is a long enough string for caching"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_function_without_string_args_executes_directly(self):
        """When no string arg > 10 chars is found, function executes without cache logic."""
        call_count = 0

        @cached(ttl=60, prefix="test")
        async def compute(number: int) -> dict:
            nonlocal call_count
            call_count += 1
            return {"value": number}

        result = await compute(42)
        assert result == {"value": 42}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_short_string_arg_skips_cache(self):
        """String args <= 10 chars are not used as cache keys."""
        call_count = 0

        @cached(ttl=60, prefix="test")
        async def compute(text: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"out": text}

        result = await compute("short")
        assert result == {"out": "short"}
        assert call_count == 1


# ─── close_redis ─────────────────────────────────────────────────────────────

class TestCloseRedis:
    @pytest.mark.asyncio
    async def test_close_redis_without_connection(self):
        """close_redis runs without error when there is no active connection."""
        cache_mod._redis_client = None
        await close_redis()
        assert cache_mod._redis_client is None
