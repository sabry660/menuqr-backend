"""AI Service API endpoints for menu generation and import."""
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.deps import TenantContext
from app.core.exceptions import AppError
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.ai import (
    GenerateRequest,
    ImportRequest,
    MenuResponseOut,
)
from app.services.ai_service import (
    generate_menu,
    import_menu,
    map_errors,
    check_tenant,
    body_hash,
    run_idempotent,
)

router = APIRouter(prefix="/ai", tags=["AI Service"])


@router.get("/health", summary="AI service health check")
async def ai_health():
    """Check if AI service is configured and ready."""
    from app.core.config import settings
    if not getattr(settings, "GROQ_API_KEY", None):
        raise AppError("AI provider not configured")
    return {"status": "healthy"}


@router.post("/menu/generate", response_model=MenuResponseOut, status_code=status.HTTP_200_OK, summary="Generate menu from brief")
async def menu_generate(
    req: GenerateRequest,
    request: Request,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_CREATE)),
    idempotency_key: Optional[str] = Header(None),
):
    """
    Generate a restaurant menu from a brief description using AI.
    
    This endpoint uses LLM to create a complete menu structure based on the provided
    prompt, cuisine type, and other parameters. The generated menu includes categories,
    items, prices, and metadata.
    """
    # Convert restaurant_id to string for AI service compatibility
    restaurant_id_str = str(req.restaurant_id)
    req.restaurant_id = restaurant_id_str
    
    # Check tenant match - use tenant_id as the identifier for AI service
    check_tenant(str(ctx.tenant_id), restaurant_id_str)
    
    # Execute with idempotency
    async def generate_with_error_handling():
        return await map_errors(generate_menu(req))
    
    result = await run_idempotent(
        str(ctx.tenant_id),
        idempotency_key,
        body_hash(req),
        generate_with_error_handling
    )
    
    result["request_id"] = getattr(request.state, "request_id", None)
    return result


@router.post("/menu/import", response_model=MenuResponseOut, status_code=status.HTTP_200_OK, summary="Import menu from document")
async def menu_import(
    req: ImportRequest,
    request: Request,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_CREATE)),
    idempotency_key: Optional[str] = Header(None),
):
    """
    Import a restaurant menu from a document (PDF/image) or raw text using AI.
    
    This endpoint uses computer vision and LLM to extract menu structure from uploaded
    documents or text. It supports PDF files, images, and raw text input.
    """
    # Convert restaurant_id to string for AI service compatibility
    restaurant_id_str = str(req.restaurant_id)
    req.restaurant_id = restaurant_id_str
    
    # Check tenant match
    check_tenant(str(ctx.tenant_id), restaurant_id_str)
    
    # Execute with idempotency
    async def import_with_error_handling():
        return await map_errors(import_menu(req))
    
    result = await run_idempotent(
        str(ctx.tenant_id),
        idempotency_key,
        body_hash(req),
        import_with_error_handling
    )
    
    result["request_id"] = getattr(request.state, "request_id", None)
    return result