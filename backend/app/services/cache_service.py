"""
Serviço de Cache com Redis para WhatsApp Insight Transcriber.
Fornece cache transparente — funciona sem Redis (fallback gracioso).
"""
import hashlib
import json
import time
import functools
from typing import Any, Optional, Callable

from app.logging import get_logger
from app.logging.error_advisor import get_error_suggestion
from app.metrics import track_cache_operation

logger = get_logger(__name__)

# Estatísticas em memória (fallback quando Redis indisponível)
_stats = {"hits": 0, "misses": 0, "errors": 0, "sets": 0}

# Conexão Redis global (lazy init)
_redis_client = None
_redis_available: Optional[bool] = None
_redis_retry_after: Optional[float] = None
REDIS_RETRY_INTERVAL = 30.0  # seconds before retrying Redis after failure


async def _get_redis():
    """Obtém conexão Redis (lazy, singleton). Retorna None se indisponível."""
    global _redis_client, _redis_available, _redis_retry_after

    # If Redis failed previously, check if retry interval has passed
    if _redis_retry_after is not None:
        if time.time() < _redis_retry_after:
            return None
        # Retry interval passed — reset and try again
        logger.info("cache.redis.retry", message="Retry interval passed, re-attempting Redis connection")
        _redis_retry_after = None
        _redis_available = None
        _redis_client = None

    if _redis_available is False:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        from app.config import settings

        if not settings.CACHE_ENABLED:
            _redis_available = False
            logger.info("Cache desabilitado via configuração (CACHE_ENABLED=false)")
            return None

        redis_url = settings.REDIS_URL
        if not redis_url:
            _redis_available = False
            logger.info("REDIS_URL não configurada — cache desabilitado")
            return None

        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        # Testar conexão
        await _redis_client.ping()
        _redis_available = True
        logger.info(f"✅ Conexão Redis estabelecida: {redis_url}")
        return _redis_client

    except Exception as e:
        _redis_retry_after = time.time() + REDIS_RETRY_INTERVAL
        _redis_client = None
        logger.warning(f"⚠️ Redis indisponível — retry em {REDIS_RETRY_INTERVAL}s: {e}")
        return None


async def close_redis():
    """Fecha conexão Redis (chamado no shutdown da app)."""
    global _redis_client, _redis_available, _redis_retry_after
    if _redis_client:
        try:
            await _redis_client.close()
        except Exception:
            pass
        _redis_client = None
        _redis_available = None
        _redis_retry_after = None


def make_cache_key(content: str, prefix: str = "wit") -> str:
    """Gera chave de cache por hash SHA256 do conteúdo."""
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"{prefix}:{content_hash}"


async def get_cached_result(key: str) -> Optional[Any]:
    """
    Busca resultado no cache.
    Retorna None se não encontrado ou Redis indisponível.
    """
    redis = await _get_redis()
    if redis is None:
        _stats["misses"] += 1
        track_cache_operation("get", "miss")
        return None

    try:
        value = await redis.get(key)
        if value is not None:
            _stats["hits"] += 1
            track_cache_operation("get", "hit")
            ttl_remaining = await redis.ttl(key)
            key_pattern = key.split(":")[0] if ":" in key else key
            logger.info(
                "cache.redis.hit",
                key_pattern=key_pattern,
                ttl=ttl_remaining,
            )
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning("cache.redis.corrupt_data", key=key[:50])
                try:
                    await redis.delete(key)
                except Exception:
                    pass
                _stats["errors"] += 1
                track_cache_operation("get", "error")
                return None
        else:
            _stats["misses"] += 1
            track_cache_operation("get", "miss")
            key_pattern = key.split(":")[0] if ":" in key else key
            logger.info(
                "cache.redis.miss",
                key_pattern=key_pattern,
            )
            return None
    except Exception as e:
        _stats["errors"] += 1
        track_cache_operation("get", "error")
        logger.error(
            "cache.redis.error",
            operation="get",
            **get_error_suggestion(exc=e),
        )
        return None


async def set_cached_result(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """
    Armazena resultado no cache com TTL configurável.
    Retorna True se sucesso, False se falha ou Redis indisponível.
    """
    redis = await _get_redis()
    if redis is None:
        track_cache_operation("set", "error")
        return False

    try:
        from app.config import settings
        effective_ttl = ttl or settings.CACHE_TTL_SECONDS

        serialized = json.dumps(value, ensure_ascii=False, default=str)
        await redis.set(key, serialized, ex=effective_ttl)
        _stats["sets"] += 1
        track_cache_operation("set", "success")
        logger.debug(f"Cache SET: {key[:50]}... (TTL={effective_ttl}s)")
        return True
    except Exception as e:
        _stats["errors"] += 1
        track_cache_operation("set", "error")
        logger.error(
            "cache.redis.error",
            operation="set",
            **get_error_suggestion(exc=e),
        )
        return False


async def invalidate_cache(key: str) -> bool:
    """Remove uma chave do cache."""
    redis = await _get_redis()
    if redis is None:
        track_cache_operation("delete", "error")
        return False

    try:
        await redis.delete(key)
        track_cache_operation("delete", "success")
        logger.debug(f"Cache INVALIDATED: {key[:50]}...")
        return True
    except Exception as e:
        _stats["errors"] += 1
        track_cache_operation("delete", "error")
        logger.warning(f"Erro ao invalidar cache ({key[:50]}...): {e}")
        return False


async def get_cache_stats() -> dict:
    """Retorna estatísticas do cache."""
    redis = await _get_redis()
    info = {}

    if redis is not None:
        try:
            redis_info = await redis.info("memory")
            info["redis_memory_used"] = redis_info.get("used_memory_human", "N/A")
            info["redis_connected"] = True
            db_size = await redis.dbsize()
            info["redis_keys"] = db_size
        except Exception:
            info["redis_connected"] = False
    else:
        info["redis_connected"] = False

    total = _stats["hits"] + _stats["misses"]
    info.update({
        "hits": _stats["hits"],
        "misses": _stats["misses"],
        "sets": _stats["sets"],
        "errors": _stats["errors"],
        "hit_rate": round(_stats["hits"] / total * 100, 1) if total > 0 else 0.0,
    })
    return info


def cached(ttl: Optional[int] = None, prefix: str = "wit"):
    """
    Decorador para cachear resultados de funções async.
    O primeiro argumento da função é usado como conteúdo para gerar a chave.

    Uso:
        @cached(ttl=3600, prefix="summary")
        async def generate_summary(text: str, ...) -> dict:
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key from all args and kwargs for uniqueness
            cache_parts = []
            for arg in args:
                if isinstance(arg, str) and len(arg) > 10:
                    cache_parts.append(arg)
                elif isinstance(arg, (int, float, bool)):
                    cache_parts.append(str(arg))
            for k, v in sorted(kwargs.items()):
                cache_parts.append(f"{k}={v}")

            if not cache_parts:
                # Sem conteúdo cacheável, executar diretamente
                return await func(*args, **kwargs)

            cache_content = "|".join(cache_parts)
            key = make_cache_key(cache_content, prefix=f"{prefix}:{func.__name__}")

            # Tentar cache
            result = await get_cached_result(key)
            if result is not None:
                logger.info(f"🎯 Cache HIT para {func.__name__}")
                return result

            # Executar função
            logger.info(f"📡 Cache MISS para {func.__name__} — chamando API")
            result = await func(*args, **kwargs)

            # Salvar no cache
            if result is not None:
                await set_cached_result(key, result, ttl=ttl)

            return result
        return wrapper
    return decorator
