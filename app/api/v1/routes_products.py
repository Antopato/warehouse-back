from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
import math



from app import db
from app.api.v1.routes_users import read_me
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductOut, ProductsResponse, ProductUpdate
from app.schemas.user import UserOut
from app.utils.db import get_db

router = APIRouter(prefix="/products", tags=["products"])


def _product_to_out(product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        code=product.code,
        name=product.name,
        description=product.description,
        category_id=product.category_id,
        category_name=product.category.name if product.category else None,
        quantity=product.quantity,
        cost=product.cost,
        price=product.price,
        location=product.location,
        created_by=product.created_by,
        creator_name=product.creator.username if product.creator else None,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/", response_model=ProductsResponse)
async def get_all_products(
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
    search: Optional[str] = None,
    category_id: Optional[str] = None,
    order_by: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
):
    query = select(Product).where(Product.deleted_at.is_(None))
    if search:
        query = query.where(
            Product.name.ilike(f"%{search}%") | Product.code.ilike(f"%{search}%")
        )
    if category_id:
        query = query.where(Product.category_id == category_id)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    if order_by == "stock_asc":
        order = Product.quantity.asc()
    elif order_by == "stock_desc":
        order = Product.quantity.desc()
    else:
        order = Product.created_at.desc()

    offset = (page - 1) * page_size
    query = query.order_by(order).offset(offset).limit(page_size)

    result = await db.execute(query)
    products = [_product_to_out(p) for p in result.scalars().all()]
    return ProductsResponse(
        products=products, 
        total=total,
        page=page, 
        page_size=page_size, 
        total_pages=math.ceil(total / page_size)
    )


@router.post("/")
async def create_product(
    form_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    existing = await db.execute(
        select(Product).where(Product.code == form_data.code, Product.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El código de producto ya existe")

    result = await db.execute(
        insert(Product)
        .values(
            code=form_data.code,
            name=form_data.name,
            description=form_data.description,
            category_id=form_data.category_id,
            quantity=form_data.quantity,
            cost=form_data.cost,
            price=form_data.price,
            location=form_data.location,
            created_by=current_user.id,
        )
        .returning(Product.id)
    )
    product_id = result.scalar()

    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Crear producto {form_data.code}",
            entity_type="Producto",
            entity_id=product_id,
        )
    )
    return {"message": "Producto creado correctamente"}


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return _product_to_out(product)


@router.put("/{product_id}")
async def update_product(
    product_id: str,
    form_data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    values = {k: v for k, v in form_data.model_dump().items() if v is not None}
    if not values:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    await db.execute(
        update(Product).where(Product.id == product_id).values(**values)
    )
    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Actualizar producto {product_id}",
            entity_type="Producto",
            entity_id=product_id,
        )
    )
    return {"message": "Producto actualizado correctamente"}


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    from datetime import datetime, timezone

    await db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Eliminar producto {product_id}",
            entity_type="Producto",
            entity_id=product_id,
        )
    )
    return {"message": "Producto eliminado correctamente"}
