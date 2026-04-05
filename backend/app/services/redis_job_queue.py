"""
Serviço de fila de jobs persistente usando Redis Streams.
Substitui a asyncio.PriorityQueue in-memory para persistência de jobs.
"""
import json
import time
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from app.logging import get_logger

logger = get_logger(__name__)

# Redis Stream keys
STREAM_KEY = "wit:jobs:stream"
GROUP_NAME = "wit-agents"
DLQ_KEY = "wit:jobs:dlq"  # Dead letter queue
STREAM_MAXLEN = 10000  # BUG 3 FIX: Cap stream size to prevent unbounded growth
DLQ_MAXLEN = 5000
MAX_DELIVERY_COUNT = 3  # BUG 5 FIX: Max retries before sending to DLQ


class RedisJobQueue:
    """
    Fila de jobs persistente usando Redis Streams.
    Garante que jobs sobrevivam restarts do servidor.
    """
    
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._initialized = False
    
    async def initialize(self, redis_client=None):
        """Inicializa a fila e cria o consumer group se necessário."""
        if redis_client:
            self._redis = redis_client
        
        if not self._redis:
            logger.warning("redis_job_queue.no_redis", reason="Redis indisponível, usando fallback in-memory")
            return False
        
        try:
            # Criar consumer group (ignora se já existe)
            try:
                await self._redis.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
                logger.info("redis_job_queue.group_created", stream=STREAM_KEY, group=GROUP_NAME)
            except Exception as e:
                if "BUSYGROUP" not in str(e):
                    raise
                # Grupo já existe - ok
            
            self._initialized = True
            logger.info("redis_job_queue.initialized")
            return True
            
        except Exception as e:
            logger.error("redis_job_queue.init_failed", error=str(e))
            return False
    
    @property
    def is_available(self) -> bool:
        return self._initialized and self._redis is not None
    
    async def enqueue(self, job_data: Dict[str, Any], priority: int = 5) -> Optional[str]:
        """
        Adiciona um job à fila Redis Stream.
        Retorna o message_id do Redis ou None se falhar.
        
        NOTE (BUG 6): priority is stored in the payload but Redis Streams
        are strictly FIFO — priority does NOT affect processing order.
        It is kept as metadata for observability/debugging only.
        """
        if not self.is_available:
            return None
        
        try:
            payload = {
                "data": json.dumps(job_data),
                "priority": str(priority),
                "enqueued_at": str(time.time()),
            }
            msg_id = await self._redis.xadd(STREAM_KEY, payload, maxlen=STREAM_MAXLEN)
            logger.debug(
                "redis_job_queue.enqueued",
                msg_id=msg_id,
                job_type=job_data.get("job_type", "unknown"),
                priority=priority,
            )
            return msg_id
        except Exception as e:
            logger.error("redis_job_queue.enqueue_failed", error=str(e))
            return None
    
    async def dequeue(self, consumer_name: str, count: int = 1, block_ms: int = 1000) -> List[Dict]:
        """
        Lê jobs da fila para um consumer específico.
        Usa XREADGROUP para consumer group semantics.
        """
        if not self.is_available:
            return []
        
        try:
            messages = await self._redis.xreadgroup(
                GROUP_NAME, consumer_name,
                {STREAM_KEY: ">"},
                count=count,
                block=block_ms,
            )
            
            results = []
            if messages:
                for stream_name, entries in messages:
                    for msg_id, fields in entries:
                        try:
                            job_data = json.loads(fields.get("data", "{}"))
                            job_data["_msg_id"] = msg_id
                            job_data["_priority"] = int(fields.get("priority", 5))
                            results.append(job_data)
                        except json.JSONDecodeError:
                            logger.error("redis_job_queue.invalid_payload", msg_id=msg_id)
                            await self.move_to_dlq(msg_id, {"raw": str(fields.get("data", ""))}, "invalid_json")
            
            return results
            
        except Exception as e:
            logger.error("redis_job_queue.dequeue_failed", error=str(e))
            return []
    
    async def ack(self, msg_id: str) -> bool:
        """Confirma processamento de um job (remove da fila de pending)."""
        if not self.is_available:
            return False
        
        try:
            await self._redis.xack(STREAM_KEY, GROUP_NAME, msg_id)
            return True
        except Exception as e:
            logger.error("redis_job_queue.ack_failed", msg_id=msg_id, error=str(e))
            return False
    
    async def move_to_dlq(self, msg_id: str, job_data: Dict, error: str):
        """Move um job falhado para a dead letter queue."""
        if not self.is_available:
            return
        
        try:
            dlq_payload = {
                "data": json.dumps(job_data),
                "error": error[:500],
                "failed_at": str(time.time()),
                "original_msg_id": msg_id,
            }
            await self._redis.xadd(DLQ_KEY, dlq_payload, maxlen=DLQ_MAXLEN)
            await self.ack(msg_id)  # Remove from pending
            logger.info("redis_job_queue.moved_to_dlq", msg_id=msg_id)
        except Exception as e:
            logger.error("redis_job_queue.dlq_failed", error=str(e))
    
    async def get_pending_count(self) -> int:
        """Retorna número de jobs pendentes na fila."""
        if not self.is_available:
            return 0
        
        try:
            info = await self._redis.xinfo_groups(STREAM_KEY)
            for group in info:
                if group.get("name") == GROUP_NAME:
                    return group.get("pending", 0)
            return 0
        except Exception:
            return 0
    
    async def get_stream_length(self) -> int:
        """Retorna tamanho total da stream."""
        if not self.is_available:
            return 0
        
        try:
            return await self._redis.xlen(STREAM_KEY)
        except Exception:
            return 0
    
    async def recover_pending(self, consumer_name: str, idle_ms: int = 60000) -> List[Dict]:
        """
        Recupera jobs que ficaram pendentes (consumer crashou) e os reatribui.
        Jobs idle por mais de idle_ms são reatribuídos ao consumer atual.
        """
        if not self.is_available:
            return []
        
        try:
            # XAUTOCLAIM: reclama mensagens idle para este consumer
            result = await self._redis.xautoclaim(
                STREAM_KEY, GROUP_NAME, consumer_name,
                min_idle_time=idle_ms,
                start_id="0-0",
                count=10,
            )
            
            # BUG 5 FIX: Check delivery count to prevent infinite retries
            pending_info = {}
            try:
                pending_details = await self._redis.xpending_range(
                    STREAM_KEY, GROUP_NAME, "-", "+", count=100,
                )
                for detail in pending_details:
                    pending_info[detail["message_id"]] = detail.get("times_delivered", 0)
            except Exception:
                pass  # Best-effort; proceed without delivery count info

            recovered = []
            if result and len(result) >= 2:
                messages = result[1]  # Segundo elemento são as mensagens
                for msg_id, fields in messages:
                    if fields:  # Pode ser None se a mensagem foi deletada
                        delivery_count = pending_info.get(msg_id, 1)
                        if delivery_count >= MAX_DELIVERY_COUNT:
                            logger.warning(
                                "redis_job_queue.max_retries_exceeded",
                                msg_id=msg_id,
                                delivery_count=delivery_count,
                            )
                            try:
                                job_data = json.loads(fields.get("data", "{}"))
                            except json.JSONDecodeError:
                                job_data = {"raw": str(fields.get("data", ""))}
                            await self.move_to_dlq(msg_id, job_data, f"max_retries_exceeded ({delivery_count})")
                            continue
                        try:
                            job_data = json.loads(fields.get("data", "{}"))
                            job_data["_msg_id"] = msg_id
                            job_data["_recovered"] = True
                            recovered.append(job_data)
                        except json.JSONDecodeError:
                            await self.move_to_dlq(msg_id, {"raw": str(fields.get("data", ""))}, "invalid_json")
            
            if recovered:
                logger.info(
                    "redis_job_queue.recovered",
                    count=len(recovered),
                    consumer=consumer_name,
                )
            
            return recovered
            
        except Exception as e:
            logger.error("redis_job_queue.recover_failed", error=str(e))
            return []


# Instância global
_job_queue: Optional[RedisJobQueue] = None
_job_queue_lock = asyncio.Lock()  # BUG 1 FIX: Prevent race condition in initialization


async def _get_job_redis():
    """BUG 4 FIX: Independent Redis connection for job queue (not shared with cache)."""
    try:
        from app.config import settings
        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            return None
        import redis.asyncio as aioredis
        client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        await client.ping()
        return client
    except Exception as e:
        logger.warning("redis_job_queue.redis_connect_failed", error=str(e))
        return None


async def get_job_queue() -> RedisJobQueue:
    """Obtém a instância global da fila de jobs com double-checked locking."""
    global _job_queue
    # BUG 1 FIX: Fast path without lock
    if _job_queue is not None:
        return _job_queue
    async with _job_queue_lock:
        # Double-check after acquiring lock
        if _job_queue is not None:
            return _job_queue
        _job_queue = RedisJobQueue()
        try:
            redis = await _get_job_redis()
            if redis:
                await _job_queue.initialize(redis)
        except Exception as e:
            logger.warning("redis_job_queue.init_fallback", error=str(e))
    return _job_queue
