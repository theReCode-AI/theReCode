from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_gemini_credential_service
from app.api.dependencies.auth import get_current_active_user
from app.db.repositories.gemini_credential_repository import GeminiCredentialNotFoundError
from app.models.user import User
from app.schemas.settings import GeminiCredentialCreate, GeminiCredentialResponse
from app.services.gemini_credential_service import GeminiCredentialService

router = APIRouter()


@router.put(
    "/gemini-key",
    response_model=GeminiCredentialResponse,
    status_code=status.HTTP_200_OK,
)
async def save_gemini_key(
    payload: GeminiCredentialCreate,
    current_user: User = Depends(get_current_active_user),
    gemini_credential_service: GeminiCredentialService = Depends(get_gemini_credential_service),
) -> GeminiCredentialResponse:
    return gemini_credential_service.save_credential(current_user.id, payload)


@router.get("/gemini-key", response_model=GeminiCredentialResponse | None)
async def get_gemini_key(
    current_user: User = Depends(get_current_active_user),
    gemini_credential_service: GeminiCredentialService = Depends(get_gemini_credential_service),
) -> GeminiCredentialResponse | None:
    return gemini_credential_service.get_credential(current_user.id)


@router.delete("/gemini-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gemini_key(
    current_user: User = Depends(get_current_active_user),
    gemini_credential_service: GeminiCredentialService = Depends(get_gemini_credential_service),
) -> None:
    try:
        gemini_credential_service.delete_credential(current_user.id)
    except GeminiCredentialNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gemini API key is not configured",
        ) from exc
