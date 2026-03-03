from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routes_users import read_me
from app.models.category import Category
from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.schemas.user import UserOut
from app.utils.db import get_db

router = APIRouter(prefix="/charts", tags=["charts"])


@router.get("/sales-by-category")
async def sales_by_category(
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    query = (
        select(
            Category.name.label("category"),
            func.sum(SaleItem.quantity).label("quantity"),
        )
        .join(Product, Product.id == SaleItem.product_id)
        .join(Category, Category.id == Product.category_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.deleted_at.is_(None))
        .group_by(Category.name)
        .order_by(func.sum(SaleItem.quantity).desc())
    )
    result = await db.execute(query)
    rows = result.all()

    return {
        "labels": [row.category for row in rows],
        "values": [row.quantity for row in rows],
    }


@router.get("/daily-margin")
async def daily_margin(
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=29)
    date_col = cast(Sale.created_at, Date).label("date")

    query = (
        select(
            date_col,
            func.sum(Sale.total_price - Sale.total_cost).label("margin"),
        )
        .where(
            Sale.deleted_at.is_(None),
            cast(Sale.created_at, Date) >= since,
        )
        .group_by(date_col)
        .order_by(date_col)
    )
    result = await db.execute(query)
    margin_by_date = {row.date: round(row.margin, 2) for row in result.all()}

    labels = []
    values = []
    for i in range(30):
        day = since + timedelta(days=i)
        labels.append(day.isoformat())
        values.append(margin_by_date.get(day, 0.0))

    return {"labels": labels, "values": values}
