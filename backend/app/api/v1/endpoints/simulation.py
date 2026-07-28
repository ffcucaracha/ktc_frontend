from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.api.dependencies import (
    get_simulation_gateway,
    require_operator,
    websocket_current_user,
)
from app.api.errors import ApiError
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.integrations.simulation.base import SimulationGateway
from app.integrations.simulation.errors import (
    IntegrationErrorCode,
    SimulationIntegrationError,
)
from app.models import User, UserRole
from app.schemas.simulation import (
    SimulationCommandRequest,
    SimulationCommandResponse,
    SimulationSessionCreateRequest,
    SimulationSessionResponse,
    SimulationStateResponse,
    SimulatorListResponse,
    SimulatorResponse,
)
from app.services.simulation import (
    DuplicateCommandError,
    InvalidCommandError,
    InvalidSessionOperationError,
    SimulationService,
    SimulationSessionNotFoundError,
    SimulatorNotFoundError,
    StaleStateRevisionError,
)

router = APIRouter(tags=["simulation"])
ws_router = APIRouter(tags=["simulation-websocket"])


def simulator_not_found_error() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "SIMULATOR_NOT_FOUND", "Тренажёр не найден")


def session_not_found_error() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "Сессия не найдена")


def invalid_operation_error() -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, "INVALID_OPERATION", "Операция недоступна")


def invalid_command_error() -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, "INVALID_COMMAND", "Команда недоступна")


def duplicate_command_error() -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, "DUPLICATE_COMMAND", "Команда уже существует")


def stale_revision_error() -> ApiError:
    return ApiError(
        status.HTTP_409_CONFLICT, "STALE_STATE_REVISION", "Устаревшая ревизия состояния"
    )


def integration_error(exc: SimulationIntegrationError) -> ApiError:
    if exc.code == IntegrationErrorCode.SIMULATION_TIMEOUT:
        return ApiError(
            status.HTTP_504_GATEWAY_TIMEOUT, exc.code.value, "Сервис моделирования не ответил"
        )
    if exc.code == IntegrationErrorCode.SIMULATION_SERVICE_UNAVAILABLE:
        return ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE, exc.code.value, "Сервис моделирования недоступен"
        )
    if exc.code == IntegrationErrorCode.SIMULATION_SESSION_NOT_FOUND:
        return ApiError(
            status.HTTP_502_BAD_GATEWAY, exc.code.value, "Сессия моделирования не найдена"
        )
    return ApiError(status.HTTP_502_BAD_GATEWAY, exc.code.value, "Ошибка сервиса моделирования")


@router.get("/simulators", response_model=SimulatorListResponse)
async def list_simulators(
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[SimulationGateway, Depends(get_simulation_gateway)],
) -> SimulatorListResponse:
    del operator
    simulators = await SimulationService(session, gateway).list_simulators()
    return SimulatorListResponse(
        items=[SimulatorResponse.model_validate(simulator) for simulator in simulators],
    )


@router.get("/simulators/{simulator_id}", response_model=SimulatorResponse)
async def get_simulator(
    simulator_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[SimulationGateway, Depends(get_simulation_gateway)],
) -> SimulatorResponse:
    del operator
    try:
        simulator = await SimulationService(session, gateway).get_simulator(simulator_id)
    except SimulatorNotFoundError as exc:
        raise simulator_not_found_error() from exc
    return SimulatorResponse.model_validate(simulator)


@router.post(
    "/simulation-sessions",
    response_model=SimulationSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulation_session(
    payload: SimulationSessionCreateRequest,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[SimulationGateway, Depends(get_simulation_gateway)],
) -> SimulationSessionResponse:
    try:
        simulation_session = await SimulationService(session, gateway).create_session(
            operator_id=operator.id,
            simulator_id=payload.simulator_id,
        )
    except SimulatorNotFoundError as exc:
        raise simulator_not_found_error() from exc
    return SimulationSessionResponse.model_validate(simulation_session)


@router.get("/simulation-sessions/{session_id}", response_model=SimulationSessionResponse)
async def get_simulation_session(
    session_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[SimulationGateway, Depends(get_simulation_gateway)],
) -> SimulationSessionResponse:
    try:
        simulation_session = await SimulationService(session, gateway).get_session(
            session_id, operator.id
        )
    except SimulationSessionNotFoundError as exc:
        raise session_not_found_error() from exc
    return SimulationSessionResponse.model_validate(simulation_session)


@router.get("/simulation-sessions/{session_id}/state", response_model=SimulationStateResponse)
async def get_simulation_state(
    session_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[SimulationGateway, Depends(get_simulation_gateway)],
) -> SimulationStateResponse:
    try:
        state_payload = await SimulationService(session, gateway).get_state(session_id, operator.id)
    except SimulationSessionNotFoundError as exc:
        raise session_not_found_error() from exc
    except InvalidSessionOperationError as exc:
        raise invalid_operation_error() from exc
    except StaleStateRevisionError as exc:
        raise stale_revision_error() from exc
    except SimulationIntegrationError as exc:
        raise integration_error(exc) from exc
    return SimulationStateResponse(state=state_payload)


@router.post(
    "/simulation-sessions/{session_id}/commands",
    response_model=SimulationCommandResponse,
)
async def send_simulation_command(
    session_id: UUID,
    payload: SimulationCommandRequest,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[SimulationGateway, Depends(get_simulation_gateway)],
) -> SimulationCommandResponse:
    try:
        outcome = await SimulationService(session, gateway).send_command(
            session_id=session_id,
            operator_id=operator.id,
            command_id=payload.command_id,
            equipment_id=payload.equipment_id,
            action=payload.action,
            payload=payload.payload,
            expected_revision=payload.expected_revision,
        )
    except SimulationSessionNotFoundError as exc:
        raise session_not_found_error() from exc
    except InvalidSessionOperationError as exc:
        raise invalid_operation_error() from exc
    except InvalidCommandError as exc:
        raise invalid_command_error() from exc
    except DuplicateCommandError as exc:
        raise duplicate_command_error() from exc

    if outcome.integration_error is not None:
        raise integration_error(outcome.integration_error)
    return SimulationCommandResponse.model_validate(outcome.command)


@router.post("/simulation-sessions/{session_id}/stop", response_model=SimulationSessionResponse)
async def stop_simulation_session(
    session_id: UUID,
    operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
    gateway: Annotated[SimulationGateway, Depends(get_simulation_gateway)],
) -> SimulationSessionResponse:
    try:
        simulation_session = await SimulationService(session, gateway).stop_session(
            session_id, operator.id
        )
    except SimulationSessionNotFoundError as exc:
        raise session_not_found_error() from exc
    except InvalidSessionOperationError as exc:
        raise invalid_operation_error() from exc
    return SimulationSessionResponse.model_validate(simulation_session)


@ws_router.websocket("/ws/v1/simulation-sessions/{session_id}")
async def simulation_session_events(
    websocket: WebSocket,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    gateway: Annotated[SimulationGateway, Depends(get_simulation_gateway)],
) -> None:
    await websocket.accept()
    try:
        user = await websocket_current_user(websocket, session, settings)
        if user.role != UserRole.OPERATOR:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        simulation_session = await SimulationService(session, gateway).get_session(
            session_id, user.id
        )
        if simulation_session.external_session_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except ApiError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except SimulationSessionNotFoundError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        async for event in gateway.stream_events(simulation_session.external_session_id):
            await websocket.send_json(event.model_dump(mode="json"))
            try:
                await SimulationService(session, gateway).apply_event(session_id, user.id, event)
            except StaleStateRevisionError:
                continue
    except WebSocketDisconnect:
        return
    except SimulationIntegrationError as exc:
        await websocket.send_json(
            {
                "type": "integration.error",
                "data": {"code": exc.code.value, "message": "Ошибка сервиса моделирования"},
            },
        )
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
