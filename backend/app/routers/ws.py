"""
WebSocket endpoint para acompanhamento de progresso em tempo real.
Substitui o polling HTTP por push notifications via WebSocket.
"""
import asyncio
import json
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.auth import verify_token
from app.database import AsyncSessionLocal
from app.logging import get_logger  # BUG 11 FIX: Use structlog instead of stdlib logging

try:
    from app.metrics import set_ws_active_connections
except ImportError:
    def set_ws_active_connections(count: int) -> None:  # noqa: ARG001
        pass
from app.models import Conversation, ProcessingStatus

logger = get_logger(__name__)
router = APIRouter(tags=["websocket"])

# BUG 9 FIX: Connection limits
MAX_CONNECTIONS_PER_SESSION = 10
MAX_TOTAL_CONNECTIONS = 500

# ─── Gerenciador de Conexões ─────────────────────────────────────────────────

class ConnectionManager:
    """Gerencia conexões WebSocket agrupadas por session_id."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        # BUG 9 FIX: Enforce connection limits
        total = sum(len(items) for items in self._connections.values())
        if total >= MAX_TOTAL_CONNECTIONS:
            await websocket.close(code=4429, reason="Limite total de conexões atingido")
            return False
        session_conns = self._connections.get(session_id, set())
        if len(session_conns) >= MAX_CONNECTIONS_PER_SESSION:
            await websocket.close(code=4429, reason="Limite de conexões por sessão atingido")
            return False

        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = set()
        self._connections[session_id].add(websocket)
        set_ws_active_connections(sum(len(items) for items in self._connections.values()))
        logger.info("ws.connected", session_id=session_id, total=len(self._connections[session_id]))
        return True

    def disconnect(self, session_id: str, websocket: WebSocket):
        # BUG 10 FIX: Guard against KeyError after session deleted
        if session_id in self._connections:
            self._connections[session_id].discard(websocket)
            if not self._connections[session_id]:
                del self._connections[session_id]
        set_ws_active_connections(sum(len(items) for items in self._connections.values()))
        logger.info("ws.disconnected", session_id=session_id)

    async def broadcast(self, session_id: str, data: dict):
        """Envia dados para todos os clientes conectados a uma session."""
        if session_id not in self._connections:
            return
        dead = []
        # BUG 7 FIX: Iterate over a copy to avoid RuntimeError (set changed during iteration)
        for ws in list(self._connections.get(session_id, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        # BUG 10 FIX: Guard against session being deleted between iteration and cleanup
        if session_id in self._connections:
            for ws in dead:
                self._connections[session_id].discard(ws)
        set_ws_active_connections(sum(len(items) for items in self._connections.values()))

    def has_subscribers(self, session_id: str) -> bool:
        return session_id in self._connections and len(self._connections[session_id]) > 0


manager = ConnectionManager()


async def _authenticate_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    payload = verify_token(token) if token else None
    if payload is None:
        await websocket.close(code=4401, reason="Token inválido ou ausente")
        return None

    username = payload.get("sub")
    if not username:
        await websocket.close(code=4401, reason="Token inválido")
        return None

    from app.auth import get_user_by_username, UserInfo

    async with AsyncSessionLocal() as session:
        user = await get_user_by_username(session, username)
        if user is None or not user.is_active:
            await websocket.close(code=4403, reason="Usuário inválido")
            return None
        return UserInfo(
            id=user.id,
            username=user.username,
            full_name=user.full_name or "",
            is_admin=user.is_admin,
            role=getattr(user, "role", "analyst") if hasattr(user, "role") else ("admin" if user.is_admin else "analyst"),
        )


async def _ensure_session_access(session_id: str, current_user) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            return current_user.is_admin
        return current_user.is_admin or conversation.owner_id == current_user.id


async def notify_progress(session_id: str, status: str, progress: float, message: str = "", **extra):
    """Chamado pelo processamento para notificar progresso via WebSocket."""
    data = {
        "type": "progress",
        "session_id": session_id,
        "status": status if isinstance(status, str) else status.value,
        "progress": progress,
        "message": message,
        **extra,
    }
    await manager.broadcast(session_id, data)


# ─── WebSocket Endpoint ──────────────────────────────────────────────────────

@router.websocket("/ws/progress/{session_id}")
async def ws_progress(websocket: WebSocket, session_id: str):
    """
    WebSocket para acompanhar progresso em tempo real.
    
    Conecte-se a ws://host/api/ws/progress/{session_id}
    Recebe mensagens JSON com: type, session_id, status, progress, message
    """
    current_user = await _authenticate_websocket(websocket)
    if current_user is None:
        return

    if not await _ensure_session_access(session_id, current_user):
        await websocket.close(code=4403, reason="Acesso negado")
        return

    await manager.connect(session_id, websocket)
    try:
        # Enviar estado atual se disponível
        from app.routers.conversations import _progress_store
        current = _progress_store.get(session_id)
        if current:
            await websocket.send_json({
                "type": "progress",
                "session_id": session_id,
                "status": current["status"].value if hasattr(current["status"], "value") else str(current["status"]),
                "progress": current.get("progress", 0),
                "message": current.get("message", ""),
            })

        # BUG 8 FIX: Heartbeat/zombie cleanup with receive timeout
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=120.0)
            except asyncio.TimeoutError:
                # No message in 120s — send ping to check if client is alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break  # Client is dead
                continue
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(session_id, websocket)
