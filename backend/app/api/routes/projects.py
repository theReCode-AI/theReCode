from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_git_service, get_memory_service, get_project_service
from app.api.dependencies.auth import get_current_active_user
from app.db.repositories.git_credential_repository import GitCredentialNotFoundError
from app.db.repositories.linked_repository_repository import (
    LinkedRepositoryExistsError,
    LinkedRepositoryNotFoundError,
)
from app.db.repositories.memory_repository import MemoryNotFoundError
from app.db.repositories.project_repository import ProjectNameExistsError, ProjectNotFoundError
from app.models.user import User
from app.schemas.git import (
    RepositoryCloneRequest,
    RepositoryCloneResponse,
    RepositoryValidationResponse,
)
from app.schemas.memory import MemoryEntryResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    RepositoryCreate,
    RepositoryResponse,
    RepositoryUpdate,
)
from app.services.git_service import GitService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService

router = APIRouter()


def _project_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


def _repository_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    try:
        return project_service.create_project(current_user.id, payload)
    except ProjectNameExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists",
        ) from None


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> list[ProjectResponse]:
    return project_service.list_projects(current_user.id)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    try:
        return project_service.get_project(current_user.id, project_id)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    try:
        return project_service.update_project(current_user.id, project_id, payload)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except ProjectNameExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists",
        ) from None


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> None:
    try:
        project_service.delete_project(current_user.id, project_id)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc


@router.post(
    "/{project_id}/repositories",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_repository(
    project_id: str,
    payload: RepositoryCreate,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> RepositoryResponse:
    try:
        return project_service.create_repository(current_user.id, project_id, payload)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except LinkedRepositoryExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already linked to this project",
        ) from None


@router.get("/{project_id}/repositories", response_model=list[RepositoryResponse])
async def list_repositories(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> list[RepositoryResponse]:
    try:
        return project_service.list_repositories(current_user.id, project_id)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc


@router.get("/{project_id}/repositories/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    project_id: str,
    repository_id: str,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> RepositoryResponse:
    try:
        return project_service.get_repository(current_user.id, project_id, repository_id)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except LinkedRepositoryNotFoundError as exc:
        raise _repository_not_found() from exc


@router.patch("/{project_id}/repositories/{repository_id}", response_model=RepositoryResponse)
async def update_repository(
    project_id: str,
    repository_id: str,
    payload: RepositoryUpdate,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> RepositoryResponse:
    try:
        return project_service.update_repository(
            current_user.id,
            project_id,
            repository_id,
            payload,
        )
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except LinkedRepositoryNotFoundError as exc:
        raise _repository_not_found() from exc


@router.delete(
    "/{project_id}/repositories/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_repository(
    project_id: str,
    repository_id: str,
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service),
) -> None:
    try:
        project_service.delete_repository(current_user.id, project_id, repository_id)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except LinkedRepositoryNotFoundError as exc:
        raise _repository_not_found() from exc


@router.post(
    "/{project_id}/repositories/{repository_id}/validate",
    response_model=RepositoryValidationResponse,
)
async def validate_repository(
    project_id: str,
    repository_id: str,
    current_user: User = Depends(get_current_active_user),
    git_service: GitService = Depends(get_git_service),
) -> RepositoryValidationResponse:
    try:
        result = git_service.validate_linked_repository(
            current_user.id,
            project_id,
            repository_id,
        )
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except LinkedRepositoryNotFoundError as exc:
        raise _repository_not_found() from exc
    except GitCredentialNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No credential configured for provider",
        ) from exc

    return RepositoryValidationResponse(
        valid=result.valid,
        provider=result.provider,
        full_name=result.full_name,
        default_branch=result.default_branch,
        clone_url=result.clone_url,
        html_url=result.html_url,
        message=result.message,
    )


@router.post(
    "/{project_id}/repositories/{repository_id}/clone",
    response_model=RepositoryCloneResponse,
)
async def clone_linked_repository(
    project_id: str,
    repository_id: str,
    payload: RepositoryCloneRequest,
    current_user: User = Depends(get_current_active_user),
    git_service: GitService = Depends(get_git_service),
) -> RepositoryCloneResponse:
    try:
        result = git_service.clone_linked_repository(
            current_user.id,
            project_id,
            repository_id,
            branch=payload.branch,
            run_id=payload.run_id,
        )
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except LinkedRepositoryNotFoundError as exc:
        raise _repository_not_found() from exc
    except GitCredentialNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No credential configured for provider",
        ) from exc

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message or "Clone failed",
        )

    return RepositoryCloneResponse(
        success=result.success,
        destination=str(result.destination),
        branch=result.branch,
        commit_sha=result.commit_sha,
        message=result.message,
    )


@router.get("/{project_id}/memories", response_model=list[MemoryEntryResponse])
async def list_project_memories(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemoryEntryResponse]:
    try:
        return memory_service.list_project_memories(current_user.id, project_id)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc


@router.get("/{project_id}/memories/{memory_id}", response_model=MemoryEntryResponse)
async def get_project_memory(
    project_id: str,
    memory_id: str,
    current_user: User = Depends(get_current_active_user),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryEntryResponse:
    try:
        return memory_service.get_project_memory(current_user.id, project_id, memory_id)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except MemoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
