from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.educational_measurements import router as educational_measurements_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.hanna_dataloggers import router as hanna_dataloggers_router
from app.api.routes.health import router as health_router
from app.api.routes.hanna_measurements import router as hanna_measurements_router
from app.api.routes.plant_measurements import router as plant_measurements_router
from app.api.routes.read_only import router as read_only_router
from app.api.routes.sensor_associations import router as sensor_associations_router
from app.core.config import Settings, get_settings
from app.db.mongodb import MongoDatabase


ADMIN_FRONTEND_ORIGINS = [
    "http://127.0.0.1:5600",
    "http://localhost:5600",
]


def create_app(
    settings: Settings | None = None,
    mongodb: MongoDatabase | None = None,
) -> FastAPI:
    """Create the API and keep its runtime dependencies on application state."""
    app_settings = settings or get_settings()
    database = mongodb or MongoDatabase(app_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await database.connect()
        application.state.mongodb = database
        try:
            yield
        finally:
            database.close()

    application = FastAPI(
        title=app_settings.app_name,
        description="Backend para la consulta de sensores de los huertos escolares",
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=ADMIN_FRONTEND_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/")
    async def root() -> dict[str, str]:
        return {
            "aplicacion": app_settings.app_name,
            "backend": "FastAPI",
            "estado": "funcionando",
        }

    application.include_router(health_router, prefix=app_settings.api_v1_prefix)
    application.include_router(
        read_only_router,
        prefix=app_settings.api_v1_prefix,
    )
    application.include_router(
        plant_measurements_router,
        prefix=app_settings.api_v1_prefix,
    )
    application.include_router(
        hanna_measurements_router,
        prefix=app_settings.api_v1_prefix,
    )
    application.include_router(hanna_dataloggers_router, prefix=app_settings.api_v1_prefix)
    application.include_router(campaigns_router, prefix=app_settings.api_v1_prefix)
    application.include_router(sensor_associations_router, prefix=app_settings.api_v1_prefix)
    application.include_router(educational_measurements_router, prefix=app_settings.api_v1_prefix)
    if app_settings.enable_diagnostics:
        application.include_router(
            diagnostics_router,
            prefix=app_settings.api_v1_prefix,
        )
    return application


app = create_app()
