import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.common import Page, PaginationParams
from app.schemas.tenant import QRCodeCreate, QRCodeOut, QRCodeUpdate
from app.services import qr_service

router = APIRouter(prefix="/restaurants/{restaurant_id}/qr-codes", tags=["QR Codes"])


@router.post("", response_model=QRCodeOut, status_code=status.HTTP_201_CREATED, summary="Create a QR code")
async def create_qr(
    restaurant_id: uuid.UUID,
    payload: QRCodeCreate,
    ctx: TenantContext = Depends(require_permission(Perm.QR_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    return await qr_service.create_qr(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, actor_id=ctx.user.id, payload=payload)


@router.get("", response_model=Page[QRCodeOut], summary="List QR codes")
async def list_qrs(
    restaurant_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    ctx: TenantContext = Depends(require_permission(Perm.QR_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await qr_service.list_qrs(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.create(items, total, pagination.page, pagination.page_size)


@router.get("/{qr_id}", response_model=QRCodeOut, summary="Get a QR code")
async def get_qr(
    restaurant_id: uuid.UUID,
    qr_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.QR_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await qr_service.get_qr(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, qr_id=qr_id)


@router.patch("/{qr_id}", response_model=QRCodeOut, summary="Update a QR code")
async def update_qr(
    restaurant_id: uuid.UUID,
    qr_id: uuid.UUID,
    payload: QRCodeUpdate,
    ctx: TenantContext = Depends(require_permission(Perm.QR_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await qr_service.update_qr(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, qr_id=qr_id, actor_id=ctx.user.id, payload=payload
    )


@router.post("/{qr_id}/deactivate", response_model=QRCodeOut, summary="Deactivate a QR code")
async def deactivate_qr(
    restaurant_id: uuid.UUID,
    qr_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.QR_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await qr_service.deactivate_qr(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, qr_id=qr_id, actor_id=ctx.user.id)
