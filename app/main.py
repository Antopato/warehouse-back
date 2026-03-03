import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.api.v1.routes_categories import router as categories_router
from app.api.v1.routes_charts import router as charts_router
from app.api.v1.routes_dashboard import router as dashboard_router
from app.api.v1.routes_products import router as products_router
from app.api.v1.routes_sells import router as sells_router
from app.api.v1.routes_users import router as users_router
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

    yield
    # Shutdown
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
