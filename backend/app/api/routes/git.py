from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_git_credential_service
from app.api.dependencies.auth import get_current_active_user
from app.db.repositories.git_credential_repository import GitCredentialNotFoundError
from app.models.repository import GitProvider
from app.models.user import User
from app.schemas.git import GitCredentialCreate, GitCredentialResponse
from app.services.git_credential_service import GitCredentialService

router = APIRouter()


@router.post(
    "/credentials",
    response_model=GitCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_git_credential(
    payload: GitCredentialCreate,
    current_user: User = Depends(get_current_active_user),
    git_credential_service: GitCredentialService = Depends(get_git_credential_service),
) -> GitCredentialResponse:
    return git_credential_service.save_credential(current_user.id, payload)


@router.get("/credentials", response_model=list[GitCredentialResponse])
async def list_git_credentials(
    current_user: User = Depends(get_current_active_user),
    git_credential_service: GitCredentialService = Depends(get_git_credential_service),
) -> list[GitCredentialResponse]:
    return git_credential_service.list_credentials(current_user.id)


@router.delete("/credentials/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_git_credential(
    provider: GitProvider,
    current_user: User = Depends(get_current_active_user),
    git_credential_service: GitCredentialService = Depends(get_git_credential_service),
) -> None:
    try:
        git_credential_service.delete_credential(current_user.id, provider)
    except GitCredentialNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Git credential not found",
        ) from exc
