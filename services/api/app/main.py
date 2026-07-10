from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.briefs import router as briefs_router
from app.api.routes.channels import router as channels_router
from app.api.routes.health import router as health_router
from app.api.routes.ideas import router as ideas_router
from app.api.routes.runs import router as runs_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.workspace import router as workspace_router
from app.core.database import init_db
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(workspace_router, prefix="/api")
    app.include_router(briefs_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(ideas_router, prefix="/api")
    app.include_router(channels_router, prefix="/api")
    # Public webhook endpoints are intentionally NOT under /api (no JWT).
    app.include_router(webhooks_router)

    @app.on_event("startup")
    def startup() -> None:
        init_db()

    return app


app = create_app()
