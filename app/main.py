import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.api.v1.routes_categories import router as categories_router
from app.api.v1.routes_charts import router as charts_router
from app.api.v1.routes_dashboard import router as dashboard_router
from app.api.v1.routes_products import router as products_router
from app.api.v1.routes_sells import router as sells_router
from app.api.v1.routes_users import router as users_router
from app.core.security import verify_access_token
from app.core.websocket_manager import manager, check_low_stock, send_low_stock_to
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.run_sync(Base.metadata.create_all)

    # Create default admin user if none exists
    from app.core.security import get_password_hash
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "admin@admin.com")
        )
        if not result.scalars().first():
            admin = User(
                email="admin@admin.com",
                username="admin",
                hashed_password=get_password_hash("123456"),
                roles=["worker", "manager", "admin"],
            )
            session.add(admin)
            await session.commit()

    # Start scheduler for stock alerts
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_low_stock,
        trigger=IntervalTrigger(hours=1),
        id="stock_alerts",
        name="Check low stock products",
        replace_existing=True,
    )
    scheduler.start()

    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title="Almacén API",
    description="API para la gestión de almacén",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
environment = os.getenv("ENVIRONMENT", "development")

origins = [frontend_url]
if environment == "development":
    origins.extend([
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(users_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(sells_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(charts_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Almacén API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok", "environment": environment}


# --- WebSocket ---

@app.websocket("/ws/alerts")
async def websocket_alerts(
    websocket: WebSocket,
    token: str = Query(...),
):
    # Authenticate via query parameter
    result = verify_access_token(token)
    if result is None:
        await websocket.close(code=4001, reason="Token invalido o expirado")
        return

    user_email, token_version = result

    # Validate token version against DB
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        db_result = await session.execute(
            select(User).where(User.email == user_email, User.deleted_at.is_(None))
        )
        user = db_result.scalar_one_or_none()
        if not user or (token_version is not None and user.token_version != token_version):
            await websocket.close(code=4001, reason="Token invalidado")
            return

    connection_id = await manager.connect(websocket)

    # Send current alerts immediately on connect
    try:
        await send_low_stock_to(connection_id)
    except Exception:
        pass

    # Keep connection alive
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
