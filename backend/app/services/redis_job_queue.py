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
        """
        if not self.is_available:
            return None
        
        try:
            payload = {
                "data": json.dumps(job_data),
                "priority": str(priority),
                "enqueued_at": str(time.time()),
            }
            msg_id = await self._redis.xadd(STREAM_KEY, payload)
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
                            await self.ack(msg_id)
            
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
            await self._redis.xadd(DLQ_KEY, dlq_payload)
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
            
            recovered = []
            if result and len(result) >= 2:
                messages = result[1]  # Segundo elemento são as mensagens
                for msg_id, fields in messages:
                    if fields:  # Pode ser None se a mensagem foi deletada
                        try:
                            job_data = json.loads(fields.get("data", "{}"))
                            job_data["_msg_id"] = msg_id
                            job_data["_recovered"] = True
                            recovered.append(job_data)
                        except json.JSONDecodeError:
                            await self.ack(msg_id)
            
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


async def get_job_queue() -> RedisJobQueue:
    """Obtém a instância global da fila de jobs."""
    global _job_queue
    if _job_queue is None:
        _job_queue = RedisJobQueue()
        try:
            from app.services.cache_service import _get_redis
            redis = await _get_redis()
            if redis:
                await _job_queue.initialize(redis)
        except Exception as e:
            logger.warning(f"redis_job_queue.init_fallback: {e}")
    return _job_queue
