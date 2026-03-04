from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_admin
from app.api.v1.routes_users import read_me
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.schemas.sale import (
    SaleCreate,
    SaleDetailResponse,
    SaleItemOut,
    SaleOut,
    SalesResponse,
    SaleUpdate,
)
from app.schemas.user import UserOut
from app.utils.db import get_db

router = APIRouter(prefix="/sales", tags=["sales"])


def _sale_to_out(sale: Sale) -> SaleOut:
    return SaleOut(
        id=sale.id,
        total_price=sale.total_price,
        total_cost=sale.total_cost,
        sold_by=sale.sold_by,
        sold_by_name=sale.seller.username if sale.seller else None,
        created_at=sale.created_at,
        updated_at=sale.updated_at,
        items=[
            SaleItemOut(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name if item.product else None,
                quantity=item.quantity,
                unit_price=item.unit_price,
                unit_cost=item.unit_cost,
            )
            for item in sale.items
        ],
    )


@router.get("/", response_model=SalesResponse)
async def get_all_sales(
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    query = (
        select(Sale)
        .where(Sale.deleted_at.is_(None))
        .order_by(Sale.created_at.desc())
    )
    result = await db.execute(query)
    sales = [_sale_to_out(s) for s in result.scalars().all()]
    return SalesResponse(sales=sales)


@router.get("/{sale_id}", response_model=SaleDetailResponse)
async def get_sale(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    result = await db.execute(
        select(Sale).where(Sale.id == sale_id, Sale.deleted_at.is_(None))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return SaleDetailResponse(sale=_sale_to_out(sale))


@router.post("/")
async def create_sale(
    form_data: SaleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    if not form_data.items:
        raise HTTPException(status_code=400, detail="La venta debe tener al menos un item")

    total_price = sum(item.quantity * item.unit_price for item in form_data.items)
    total_cost = sum(item.quantity * item.unit_cost for item in form_data.items)

    result = await db.execute(
        insert(Sale)
        .values(total_price=total_price, total_cost=total_cost, sold_by=current_user.id)
        .returning(Sale.id)
    )
    sale_id = result.scalar()

    for item in form_data.items:
        product = await db.get(Product, item.product_id)
        if not product or product.deleted_at is not None:
            raise HTTPException(status_code=404, detail=f"Producto {item.product_id} no encontrado")
        if product.quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para '{product.name}': disponible {product.quantity}, solicitado {item.quantity}",
            )

        product.quantity -= item.quantity

        await db.execute(
            insert(SaleItem).values(
                sale_id=sale_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                unit_cost=item.unit_cost,
            )
        )

    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Crear venta {sale_id}",
            entity_type="Venta",
            entity_id=sale_id,
        )
    )
    return {"message": "Venta registrada correctamente"}


@router.put("/{sale_id}")
async def update_sale(
    sale_id: str,
    form_data: SaleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(require_admin),
):
    result = await db.execute(
        select(Sale).where(Sale.id == sale_id, Sale.deleted_at.is_(None))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    if not form_data.items:
        raise HTTPException(status_code=400, detail="La venta debe tener al menos un item")

    # Delete old items
    await db.execute(delete(SaleItem).where(SaleItem.sale_id == sale_id))

    # Insert new items
    total_price = 0.0
    total_cost = 0.0
    for item in form_data.items:
        await db.execute(
            insert(SaleItem).values(
                sale_id=sale_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                unit_cost=item.unit_cost,
            )
        )
        total_price += item.quantity * item.unit_price
        total_cost += item.quantity * item.unit_cost

    # Update sale totals
    await db.execute(
        update(Sale).where(Sale.id == sale_id).values(
            total_price=total_price, total_cost=total_cost
        )
    )

    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Actualizar venta {sale_id}",
            entity_type="Venta",
            entity_id=sale_id,
        )
    )
    return {"message": "Venta actualizada correctamente"}


@router.delete("/{sale_id}")
async def delete_sale(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(require_admin),
):
    result = await db.execute(
        select(Sale).where(Sale.id == sale_id, Sale.deleted_at.is_(None))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    await db.execute(
        update(Sale)
        .where(Sale.id == sale_id)
        .values(deleted_at=datetime.now(timezone.utc))
    )

    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Eliminar venta {sale_id}",
            entity_type="Venta",
            entity_id=sale_id,
        )
    )
    return {"message": "Venta eliminada correctamente"}
