from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import insert, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routes_users import read_me
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.schemas.category import (
    CategoriesResponse,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
)
from app.schemas.user import UserOut
from app.utils.db import get_db

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", response_model=CategoriesResponse)
async def get_all_categories(
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = None,
):
    query = select(Category).order_by(Category.name)
    if search:
        query = query.where(Category.name.ilike(f"%{search}%"))
    result = await db.execute(query)
    categories = [CategoryOut.model_validate(c) for c in result.scalars().all()]
    return CategoriesResponse(categories=categories)


@router.post("/")
async def create_category(
    form_data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    existing = await db.execute(
        select(Category).where(Category.name == form_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="La categoría ya existe")

    result = await db.execute(
        insert(Category)
        .values(name=form_data.name, description=form_data.description)
        .returning(Category.id)
    )
    category_id = result.scalar()

    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Crear categoría {form_data.name}",
            entity_type="Categoría",
            entity_id=category_id,
        )
    )
    return {"message": "Categoría creada correctamente"}


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(category_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return CategoryOut.model_validate(category)


@router.put("/{category_id}")
async def update_category(
    category_id: str,
    form_data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    values = {k: v for k, v in form_data.model_dump().items() if v is not None}
    if not values:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    await db.execute(
        update(Category).where(Category.id == category_id).values(**values)
    )
    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Actualizar categoría {category_id}",
            entity_type="Categoría",
            entity_id=category_id,
        )
    )
    return {"message": "Categoría actualizada correctamente"}


@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    await db.execute(delete(Category).where(Category.id == category_id))
    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Eliminar categoría {category_id}",
            entity_type="Categoría",
            entity_id=category_id,
        )
    )
    return {"message": "Categoría eliminada correctamente"}
