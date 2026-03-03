from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_access_token,
    verify_password,
)
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserListed,
    UserLogin,
    UserOut,
    UserUpdate,
    UsersResponse,
)
from app.utils.db import get_db

router = APIRouter(prefix="/users", tags=["users"])


async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no proporcionado")
    token = authorization.split(" ")[1]
    result = verify_access_token(token)
    if result is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    email, token_version = result
    query = select(User).where(User.email == email, User.deleted_at.is_(None))
    db_result = await db.execute(query)
    user = db_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if token_version is not None and user.token_version != token_version:
        raise HTTPException(status_code=401, detail="Token invalidado")
    return user


async def read_me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    return UserOut.model_validate(current_user)


@router.post("/register")
async def register(
    form_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=403, detail="Solo los administradores pueden crear usuarios"
        )
    existing = await db.execute(select(User).where(User.email == form_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    hashed = get_password_hash(form_data.password)
    result = await db.execute(
        insert(User)
        .values(
            email=form_data.email,
            username=form_data.username,
            hashed_password=hashed,
            roles=form_data.roles,
        )
        .returning(User.id)
    )
    user_id = result.scalar()

    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Registrar usuario {form_data.email}",
            entity_type="Usuario",
            entity_id=user_id,
        )
    )
    return {"message": "Usuario registrado correctamente"}


@router.post("/login")
async def login(form_data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.email == form_data.email, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    access_token = create_access_token(
        data={"sub": user.email}, token_version=user.token_version
    )
    refresh_token = generate_refresh_token()
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserOut.model_validate(user).model_dump(mode="json"),
    }


@router.post("/token/refresh")
async def refresh_token(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no proporcionado")
    token = authorization.split(" ")[1]
    result = verify_access_token(token)
    if result is not None:
        return {"access_token": token, "token_type": "bearer"}

    raise HTTPException(status_code=401, detail="No se pudo renovar el token")


@router.get("/me", response_model=UserOut)
async def get_me(current_user: UserOut = Depends(read_me)):
    return current_user


@router.get("/", response_model=UsersResponse)
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    query = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    result = await db.execute(query)
    users = [UserListed.model_validate(u) for u in result.scalars().all()]
    return UsersResponse(users=users)


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    form_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    if "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Solo administradores")

    values = {k: v for k, v in form_data.model_dump().items() if v is not None}
    if not values:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    await db.execute(update(User).where(User.id == user_id).values(**values))
    return {"message": "Usuario actualizado correctamente"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(read_me),
):
    if "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Solo administradores")

    from datetime import datetime, timezone

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await db.execute(
        insert(AuditLog).values(
            user_id=current_user.id,
            action=f"Eliminar usuario {user_id}",
            entity_type="Usuario",
            entity_id=user_id,
        )
    )
    return {"message": "Usuario eliminado correctamente"}
