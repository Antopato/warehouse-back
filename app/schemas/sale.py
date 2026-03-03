from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SaleItemCreate(BaseModel):
    product_id: UUID
    quantity: int
    unit_price: float
    unit_cost: float


class SaleCreate(BaseModel):
    items: list[SaleItemCreate]


class SaleItemUpdate(BaseModel):
    product_id: UUID
    quantity: int
    unit_price: float
    unit_cost: float


class SaleUpdate(BaseModel):
    items: list[SaleItemUpdate]


class SaleItemOut(BaseModel):
    id: UUID
    product_id: UUID
    product_name: Optional[str] = None
    quantity: int
    unit_price: float
    unit_cost: float

    model_config = {"from_attributes": True}


class SaleOut(BaseModel):
    id: UUID
    total_price: float
    total_cost: float
    sold_by: Optional[UUID]
    sold_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: list[SaleItemOut]

    model_config = {"from_attributes": True}


class SalesResponse(BaseModel):
    sales: list[SaleOut]


class SaleDetailResponse(BaseModel):
    sale: SaleOut
