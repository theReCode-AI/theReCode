from fastapi import APIRouter

from app.api.routes import auth, chat, git, health, projects, runs

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(git.router, prefix="/git", tags=["git"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(chat.router, prefix="/runs", tags=["chat"])
