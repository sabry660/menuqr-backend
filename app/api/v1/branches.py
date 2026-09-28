import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.common import Page, PaginationParams
from app.schemas.restaurant import BranchCreate, BranchOut, BranchUpdate
from app.services import branch_service

router = APIRouter(prefix="/restaurants/{restaurant_id}/branches", tags=["Branches"])


@router.post("", response_model=BranchOut, status_code=status.HTTP_201_CREATED, summary="Create a branch")
async def create_branch(
    restaurant_id: uuid.UUID,
    payload: BranchCreate,
    ctx: TenantContext = Depends(require_permission(Perm.BRANCH_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    return await branch_service.create_branch(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, actor_id=ctx.user.id, payload=payload
    )


@router.get("", response_model=Page[BranchOut], summary="List branches")
async def list_branches(
    restaurant_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    ctx: TenantContext = Depends(require_permission(Perm.BRANCH_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await branch_service.list_branches(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.create(items, total, pagination.page, pagination.page_size)


@router.get("/{branch_id}", response_model=BranchOut, summary="Get a branch")
async def get_branch(
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.BRANCH_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await branch_service.get_branch(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, branch_id=branch_id)


@router.patch("/{branch_id}", response_model=BranchOut, summary="Update a branch")
async def update_branch(
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    ctx: TenantContext = Depends(require_permission(Perm.BRANCH_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await branch_service.update_branch(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, branch_id=branch_id, actor_id=ctx.user.id, payload=payload
    )


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive a branch")
async def delete_branch(
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.BRANCH_DELETE)),
    db: AsyncSession = Depends(get_db),
):
    await branch_service.delete_branch(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, branch_id=branch_id, actor_id=ctx.user.id
    )
