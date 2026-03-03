import uuid
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.product import Product

LOW_STOCK_THRESHOLD = 10


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self._connections[connection_id] = websocket
        return connection_id

    def disconnect(self, connection_id: str):
        self._connections.pop(connection_id, None)

    async def send_to(self, connection_id: str, message: dict):
        ws = self._connections.get(connection_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(connection_id)

    async def broadcast(self, message: dict):
        disconnected = []
        for conn_id, ws in self._connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(conn_id)
        for conn_id in disconnected:
            self.disconnect(conn_id)


manager = ConnectionManager()


def _build_alerts_message(products) -> dict:
    alerts = [
        {
            "code": p.code,
            "name": p.name,
            "quantity": p.quantity,
            "location": p.location,
            "severity": "critical" if p.quantity == 0 else "warning",
        }
        for p in products
    ]
    return {
        "type": "stock_alerts",
        "alerts": alerts,
        "count": len(alerts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _query_low_stock():
    async with AsyncSessionLocal() as session:
        query = (
            select(Product)
            .where(
                Product.deleted_at.is_(None),
                Product.quantity <= LOW_STOCK_THRESHOLD,
            )
            .order_by(Product.quantity.asc())
        )
        result = await session.execute(query)
        return result.scalars().all()


async def check_low_stock():
    """Tarea programada: consulta productos con stock bajo y broadcast a todos."""
    products = await _query_low_stock()
    await manager.broadcast(_build_alerts_message(products))


async def send_low_stock_to(connection_id: str):
    """Envia alertas actuales a un cliente recién conectado."""
    products = await _query_low_stock()
    await manager.send_to(connection_id, _build_alerts_message(products))
