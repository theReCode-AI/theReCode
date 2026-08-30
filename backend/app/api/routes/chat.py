from fastapi import APIRouter, Depends, HTTPException, status
from google.genai.errors import ClientError

from app.api.dependencies import get_chat_service
from app.api.dependencies.auth import get_current_active_user
from app.db.repositories.project_repository import ProjectNotFoundError
from app.db.repositories.run_repository import RunNotFoundError
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatSendResponse
from app.services.chat_service import ChatService
from app.services.gemini_chat_client import GeminiChatError

router = APIRouter()


def _run_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")


def _project_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


@router.get("/{run_id}/chat/messages", response_model=list[ChatMessageResponse])
async def list_chat_messages(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ChatMessageResponse]:
    try:
        return chat_service.list_messages(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc


@router.post("/{run_id}/chat/messages", response_model=ChatSendResponse)
async def send_chat_message(
    run_id: str,
    payload: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatSendResponse:
    try:
        return chat_service.send_message(current_user.id, run_id, payload.content)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
    except GeminiChatError as exc:
        if isinstance(exc.__cause__, ClientError) and getattr(exc.__cause__, "code", None) == 429:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini rate limit exceeded. Try again shortly.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/{run_id}/chat/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_messages(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    try:
        chat_service.clear_messages(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc
