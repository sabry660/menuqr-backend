import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.restaurant import Branch, Restaurant
from app.models.misc import QRCode
from app.schemas.tenant import QRCodeCreate, QRCodeUpdate
from app.services import audit_service


async def _owned_restaurant(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID) -> Restaurant:
    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.tenant_id == tenant_id))
    restaurant = result.scalar_one_or_none()
    if restaurant is None:
        raise NotFoundError("Restaurant not found.")
    return restaurant


async def _owned_qr(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, qr_id: uuid.UUID) -> QRCode:
    result = await db.execute(
        select(QRCode)
        .join(Restaurant, Restaurant.id == QRCode.restaurant_id)
        .where(QRCode.id == qr_id, QRCode.restaurant_id == restaurant_id, Restaurant.tenant_id == tenant_id)
    )
    qr = result.scalar_one_or_none()
    if qr is None:
        raise NotFoundError("QR code not found.")
    return qr


async def create_qr(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, actor_id: uuid.UUID, payload: QRCodeCreate
) -> QRCode:
    restaurant = await _owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)

    if payload.branch_id is not None:
        branch_result = await db.execute(
            select(Branch).where(Branch.id == payload.branch_id, Branch.restaurant_id == restaurant_id)
        )
        if branch_result.scalar_one_or_none() is None:
            raise ValidationAppError("branch_id does not belong to this restaurant.")

    target_url = f"{settings.FRONTEND_URL}/menu/{restaurant.slug}"
    qr = QRCode(restaurant_id=restaurant_id, branch_id=payload.branch_id, label=payload.label, target_url=target_url)
    db.add(qr)
    await db.flush()
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="qr.created",
        resource_type="qr_code", resource_id=str(qr.id),
    )
    await db.commit()
    await db.refresh(qr)
    return qr


async def list_qrs(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, offset: int, limit: int):
    await _owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    total = (await db.execute(select(func.count()).select_from(QRCode).where(QRCode.restaurant_id == restaurant_id))).scalar_one()
    result = await db.execute(
        select(QRCode).where(QRCode.restaurant_id == restaurant_id).order_by(QRCode.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_qr(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, qr_id: uuid.UUID) -> QRCode:
    return await _owned_qr(db, tenant_id=tenant_id, restaurant_id=restaurant_id, qr_id=qr_id)


async def update_qr(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, qr_id: uuid.UUID, actor_id: uuid.UUID, payload: QRCodeUpdate
) -> QRCode:
    qr = await _owned_qr(db, tenant_id=tenant_id, restaurant_id=restaurant_id, qr_id=qr_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(qr, field, value)
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="qr.updated",
        resource_type="qr_code", resource_id=str(qr.id), metadata={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(qr)
    return qr


async def deactivate_qr(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, qr_id: uuid.UUID, actor_id: uuid.UUID) -> QRCode:
    qr = await _owned_qr(db, tenant_id=tenant_id, restaurant_id=restaurant_id, qr_id=qr_id)
    qr.status = "inactive"
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="qr.deactivated",
        resource_type="qr_code", resource_id=str(qr.id),
    )
    await db.commit()
    await db.refresh(qr)
    return qr
