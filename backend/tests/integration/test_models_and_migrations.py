from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.time import utc_now
from app.models import (
    LoginEvent,
    RefreshToken,
    SimulationCommand,
    SimulationCommandStatus,
    SimulationSession,
    SimulationSessionStatus,
    SimulatorDefinition,
    User,
    UserRole,
)


@pytest.mark.asyncio
async def test_user_constraints_enforce_role_and_unique_username(
    postgres_session_factory: async_sessionmaker,
) -> None:
    async with postgres_session_factory() as session:
        session.add(
            User(
                username="operator-1",
                full_name="Operator One",
                role=UserRole.OPERATOR,
                password_hash="hash-1",
            ),
        )
        await session.commit()

        session.add(
            User(
                username="operator-1",
                full_name="Operator Duplicate",
                role=UserRole.OPERATOR,
                password_hash="hash-2",
            ),
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    async with postgres_session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(User).values(
                    id=uuid4(),
                    username="bad-role",
                    full_name="Bad Role",
                    role="manager",
                    password_hash="hash",
                    is_active=True,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                ),
            )
            await session.commit()


@pytest.mark.asyncio
async def test_jsonb_columns_and_foreign_keys(
    postgres_session_factory: async_sessionmaker,
) -> None:
    async with postgres_session_factory() as session:
        operator = User(
            username="operator-2",
            full_name="Operator Two",
            role=UserRole.OPERATOR,
            password_hash="hash",
        )
        simulator = SimulatorDefinition(
            code="boiler-test",
            external_id="boiler-test-external",
            name="Boiler Test",
            description="Test simulator",
            visualization_type="boiler-v1",
            is_active=True,
        )
        session.add_all([operator, simulator])
        await session.flush()

        simulation_session = SimulationSession(
            operator_id=operator.id,
            simulator_definition_id=simulator.id,
            external_session_id="external-session-test",
            status=SimulationSessionStatus.ACTIVE,
            started_at=utc_now(),
            last_state={"revision": 1, "equipment": {}},
        )
        session.add(simulation_session)
        await session.flush()

        command = SimulationCommand(
            session_id=simulation_session.id,
            command_id=uuid4(),
            equipment_id="steam_supply_pump",
            action="start",
            payload={"expected_revision": 1},
            status=SimulationCommandStatus.PENDING,
        )
        session.add(command)
        await session.commit()

        state_type = await session.scalar(
            text(
                "select pg_typeof(last_state)::text "
                "from simulation_sessions where id = :session_id",
            ),
            {"session_id": simulation_session.id},
        )
        payload_type = await session.scalar(
            text(
                "select pg_typeof(payload)::text from simulation_commands where id = :command_id",
            ),
            {"command_id": command.id},
        )

    assert state_type == "jsonb"
    assert payload_type == "jsonb"


@pytest.mark.asyncio
async def test_refresh_tokens_cascade_and_login_events_keep_audit_row(
    postgres_session_factory: async_sessionmaker,
) -> None:
    async with postgres_session_factory() as session:
        user = User(
            username="operator-3",
            full_name="Operator Three",
            role=UserRole.OPERATOR,
            password_hash="hash",
        )
        session.add(user)
        await session.flush()

        session.add(
            RefreshToken(
                user_id=user.id,
                token_hash="token-hash",
                expires_at=utc_now() + timedelta(days=14),
            ),
        )
        login_event = LoginEvent(
            user_id=user.id,
            username_entered=user.username,
            success=True,
        )
        session.add(login_event)
        await session.commit()

        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()

    async with postgres_session_factory() as session:
        refresh_count = await session.scalar(select(func.count()).select_from(RefreshToken))
        saved_login_event = await session.scalar(select(LoginEvent))

    assert refresh_count == 0
    assert saved_login_event is not None
    assert saved_login_event.user_id is None
