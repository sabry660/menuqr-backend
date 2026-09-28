from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.public import PublicRestaurantMenu
from app.services import public_service

router = APIRouter(prefix="/public", tags=["Public Menu"])


@router.get(
    "/{restaurant_slug}/menu",
    response_model=PublicRestaurantMenu,
    summary="Get a restaurant's published public menu (no authentication required)",
)
async def get_public_menu(restaurant_slug: str, db: AsyncSession = Depends(get_db)):
    return await public_service.get_public_menu(db, restaurant_slug=restaurant_slug)
