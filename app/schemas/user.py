from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    roles: Optional[list[str]] = ["worker"]


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    username: str
    roles: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListed(BaseModel):
    id: UUID
    email: str
    username: str
    roles: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UsersResponse(BaseModel):
    users: list[UserListed]


class UserUpdate(BaseModel):
    username: Optional[str] = None
    roles: Optional[list[str]] = None
