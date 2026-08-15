from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import configure_error_handlers
from app.api.v1.endpoints.assessment import router as assessment_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.operators import router as operators_router
from app.api.v1.endpoints.simulation import router as simulation_router
from app.api.v1.endpoints.simulation import ws_router as simulation_ws_router
from app.core.config import get_settings
from app.core.cors import configure_cors
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal, engine
from app.integrations.simulation.factory import create_simulation_gateway
from app.services.simulation_telemetry import SimulationTelemetryCollector


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    collector: SimulationTelemetryCollector | None = getattr(
        app.state,
        "simulation_telemetry_collector",
        None,
    )
    if collector is not None:
        await collector.start()
    try:
        yield
    finally:
        if collector is not None:
            await collector.stop()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    if settings.simulation_telemetry_enabled:
        app.state.simulation_telemetry_collector = SimulationTelemetryCollector(
            AsyncSessionLocal,
            create_simulation_gateway(settings),
            polling_interval_seconds=settings.simulation_telemetry_interval_seconds,
            discovery_interval_seconds=settings.simulation_telemetry_discovery_interval_seconds,
        )

    configure_cors(app, settings.cors_origin_list)
    configure_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(operators_router, prefix="/api/v1")
    app.include_router(simulation_router, prefix="/api/v1")
    app.include_router(assessment_router, prefix="/api/v1")
    app.include_router(simulation_ws_router)
    return app


app = create_app()
