"""
WebSocket endpoint para acompanhamento de progresso em tempo real.
Substitui o polling HTTP por push notifications via WebSocket.
"""
import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models import ProcessingStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# ─── Gerenciador de Conexões ─────────────────────────────────────────────────

class ConnectionManager:
    """Gerencia conexões WebSocket agrupadas por session_id."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = set()
        self._connections[session_id].add(websocket)
        logger.info(f"WS conectado: session={session_id}, total={len(self._connections[session_id])}")

    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self._connections:
            self._connections[session_id].discard(websocket)
            if not self._connections[session_id]:
                del self._connections[session_id]
        logger.info(f"WS desconectado: session={session_id}")

    async def broadcast(self, session_id: str, data: dict):
        """Envia dados para todos os clientes conectados a uma session."""
        if session_id not in self._connections:
            return
        dead = []
        for ws in self._connections[session_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[session_id].discard(ws)

    def has_subscribers(self, session_id: str) -> bool:
        return session_id in self._connections and len(self._connections[session_id]) > 0


manager = ConnectionManager()


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

        # Manter conexão aberta, responder a pings
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(session_id, websocket)
