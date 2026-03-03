from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProductCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    quantity: int = 0
    cost: float = 0.0
    price: float = 0.0
    location: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    quantity: Optional[int] = None
    cost: Optional[float] = None
    price: Optional[float] = None
    location: Optional[str] = None


class ProductOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: Optional[str]
    category_id: Optional[UUID]
    category_name: Optional[str] = None
    quantity: int
    cost: float
    price: float
    location: Optional[str]
    created_by: Optional[UUID]
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductsResponse(BaseModel):
    products: list[ProductOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProductListed(BaseModel):
    id: UUID
    code: str
    name: str
    category_name: Optional[str] = None
    quantity: int
    cost: float
    price: float
    location: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
