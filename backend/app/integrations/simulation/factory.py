from functools import lru_cache

from app.core.config import Settings, get_settings
from app.integrations.simulation.base import SimulationGateway
from app.integrations.simulation.errors import SimulationProtocolError
from app.integrations.simulation.http_gateway import HttpSimulationGateway
from app.integrations.simulation.ktc_gateway import KtcOilHeatingElouGateway, KtcOilHeatingGateway
from app.integrations.simulation.mock_gateway import MockSimulationGateway
from app.integrations.simulation.routing_gateway import RoutingSimulationGateway


@lru_cache(maxsize=1)
def get_mock_simulation_gateway() -> MockSimulationGateway:
    return MockSimulationGateway()


@lru_cache(maxsize=8)
def get_ktc_oil_heating_gateway(
    ktc_api_base_url: str,
    connect_timeout_seconds: float,
    read_timeout_seconds: float,
) -> KtcOilHeatingGateway:
    settings = get_settings().model_copy(
        update={
            "ktc_api_base_url": ktc_api_base_url,
            "simulation_connect_timeout_seconds": connect_timeout_seconds,
            "simulation_read_timeout_seconds": read_timeout_seconds,
        },
    )
    return KtcOilHeatingGateway(settings)


@lru_cache(maxsize=8)
def get_ktc_oil_heating_elou_gateway(
    ktc_api_base_url: str,
    connect_timeout_seconds: float,
    read_timeout_seconds: float,
) -> KtcOilHeatingElouGateway:
    settings = get_settings().model_copy(
        update={
            "ktc_api_base_url": ktc_api_base_url,
            "simulation_connect_timeout_seconds": connect_timeout_seconds,
            "simulation_read_timeout_seconds": read_timeout_seconds,
        },
    )
    return KtcOilHeatingElouGateway(settings)


def create_default_simulation_gateway(settings: Settings) -> SimulationGateway:
    match settings.simulation_gateway_mode:
        case "mock":
            return get_mock_simulation_gateway()
        case "http":
            return HttpSimulationGateway(settings)
        case _:
            raise SimulationProtocolError()


def create_simulation_gateway(settings: Settings | None = None) -> SimulationGateway:
    resolved_settings = settings or get_settings()
    default_gateway = create_default_simulation_gateway(resolved_settings)
    ktc_gateway = get_ktc_oil_heating_gateway(
        resolved_settings.ktc_api_base_url,
        resolved_settings.simulation_connect_timeout_seconds,
        resolved_settings.simulation_read_timeout_seconds,
    )
    ktc_combined_gateway = get_ktc_oil_heating_elou_gateway(
        resolved_settings.ktc_api_base_url,
        resolved_settings.simulation_connect_timeout_seconds,
        resolved_settings.simulation_read_timeout_seconds,
    )
    return RoutingSimulationGateway(default_gateway, ktc_gateway, ktc_combined_gateway)
