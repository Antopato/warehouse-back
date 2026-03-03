from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routes_users import read_me
from app.models.category import Category
from app.models.product import Product
from app.models.sale import Sale
from app.models.user import User
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardStats,
    LowStockProduct,
    RecentProduct,
)
from app.schemas.user import UserOut
from app.utils.db import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

LOW_STOCK_THRESHOLD = 10


@router.get("/", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    # Total products
    total_products_result = await db.execute(
        select(func.count(Product.id)).where(Product.deleted_at.is_(None))
    )
    total_products = total_products_result.scalar() or 0

    # Total categories
    total_categories_result = await db.execute(select(func.count(Category.id)))
    total_categories = total_categories_result.scalar() or 0

    # Total users
    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.deleted_at.is_(None))
    )
    total_users = total_users_result.scalar() or 0

    # Total stock value
    stock_value_result = await db.execute(
        select(func.coalesce(func.sum(Product.price * Product.quantity), 0)).where(
            Product.deleted_at.is_(None)
        )
    )
    total_stock_value = float(stock_value_result.scalar() or 0)

    # Total margin (sum of total_price - total_cost from all sales)
    margin_result = await db.execute(
        select(func.coalesce(func.sum(Sale.total_price - Sale.total_cost), 0)).where(
            Sale.deleted_at.is_(None)
        )
    )
    total_margin = float(margin_result.scalar() or 0)

    # Low stock count
    low_stock_result = await db.execute(
        select(func.count(Product.id)).where(
            Product.deleted_at.is_(None),
            Product.quantity <= LOW_STOCK_THRESHOLD,
        )
    )
    low_stock_count = low_stock_result.scalar() or 0

    stats = DashboardStats(
        total_products=total_products,
        total_categories=total_categories,
        total_users=total_users,
        total_margin=total_margin,
        total_stock_value=total_stock_value,
        low_stock_count=low_stock_count,
    )

    # Low stock products
    low_stock_query = (
        select(Product)
        .where(
            Product.deleted_at.is_(None),
            Product.quantity <= LOW_STOCK_THRESHOLD,
        )
        .order_by(Product.quantity.asc())
        .limit(10)
    )
    low_stock_products_result = await db.execute(low_stock_query)
    low_stock_products = [
        LowStockProduct(
            code=p.code,
            name=p.name,
            quantity=p.quantity,
            location=p.location,
        )
        for p in low_stock_products_result.scalars().all()
    ]

    # Recent products
    recent_query = (
        select(Product)
        .where(Product.deleted_at.is_(None))
        .order_by(Product.created_at.desc())
        .limit(10)
    )
    recent_result = await db.execute(recent_query)
    recent_products = [
        RecentProduct(
            code=p.code,
            name=p.name,
            quantity=p.quantity,
            created_at=p.created_at.strftime("%d/%m/%Y %H:%M"),
        )
        for p in recent_result.scalars().all()
    ]

    return DashboardResponse(
        stats=stats,
        low_stock_products=low_stock_products,
        recent_products=recent_products,
    )
