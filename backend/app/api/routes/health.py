from fastapi import APIRouter, Depends, Response, status

from app.db.dependencies import get_mongodb_manager
from app.db.mongodb import MongoDBManager
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Return service liveness status."""
    return HealthResponse(status="ok", service="codethera-backend")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readiness(
    response: Response,
    manager: MongoDBManager = Depends(get_mongodb_manager),
) -> ReadinessResponse:
    """Return service readiness status including MongoDB connectivity."""
    mongodb_status = manager.ping()
    is_ready = mongodb_status == "ok"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ok" if is_ready else "degraded",
        checks={"mongodb": mongodb_status},
    )
