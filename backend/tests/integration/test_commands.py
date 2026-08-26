import pytest
from pwdlib import PasswordHash
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.commands.create_admin import create_admin
from app.commands.seed_e2e_admin import seed_e2e_admin, seed_e2e_operator
from app.commands.seed_simulators import seed_simulators
from app.models import SimulatorDefinition, User, UserRole
from app.repositories.simulators import (
    BOILER_DEMO_CODE,
    KTC_OIL_HEATING_CODE,
    KTC_OIL_HEATING_ELOU_CODE,
)


@pytest.mark.asyncio
async def test_seed_simulators_is_idempotent(
    postgres_session_factory: async_sessionmaker,
) -> None:
    first = await seed_simulators(postgres_session_factory)
    second = await seed_simulators(postgres_session_factory)

    async with postgres_session_factory() as session:
        simulator_count = await session.scalar(
            select(func.count()).select_from(SimulatorDefinition),
        )
        simulator = await session.scalar(
            select(SimulatorDefinition).where(SimulatorDefinition.code == BOILER_DEMO_CODE),
        )
        ktc_simulator = await session.scalar(
            select(SimulatorDefinition).where(
                SimulatorDefinition.code == KTC_OIL_HEATING_CODE,
            ),
        )
        combined_simulator = await session.scalar(
            select(SimulatorDefinition).where(
                SimulatorDefinition.code == KTC_OIL_HEATING_ELOU_CODE,
            ),
        )

    assert [item.id for item in first] == [item.id for item in second]
    assert simulator_count == 3
    assert simulator is not None
    assert simulator.external_id == "boiler-001"
    assert simulator.visualization_type == "boiler-v1"
    assert simulator.is_active is True
    assert ktc_simulator is not None
    assert ktc_simulator.external_id == "ktc-oil-heating"
    assert ktc_simulator.visualization_type == "oil-heating-v1"
    assert ktc_simulator.is_active is True
    assert combined_simulator is not None
    assert combined_simulator.external_id == "ktc-oil-heating-elou"
    assert combined_simulator.visualization_type == "oil-heating-elou-v1"
    assert combined_simulator.is_active is True


@pytest.mark.asyncio
async def test_create_admin_creates_active_admin_without_hardcoded_password(
    postgres_session_factory: async_sessionmaker,
) -> None:
    result = await create_admin(
        session_factory=postgres_session_factory,
        username="admin",
        full_name="Admin User",
        password=None,
    )

    assert result.created is True
    assert result.temporary_password is not None
    assert len(result.temporary_password) == 24

    async with postgres_session_factory() as session:
        admin = await session.scalar(select(User).where(User.username == "admin"))

    assert admin is not None
    assert admin.role == UserRole.ADMIN
    assert admin.is_active is True
    assert admin.password_hash != result.temporary_password
    assert PasswordHash.recommended().verify(result.temporary_password, admin.password_hash)


@pytest.mark.asyncio
async def test_create_admin_is_idempotent_and_returns_password_once(
    postgres_session_factory: async_sessionmaker,
) -> None:
    first = await create_admin(
        session_factory=postgres_session_factory,
        username="admin",
        full_name="Admin User",
        password="provided-admin-password",
    )
    second = await create_admin(
        session_factory=postgres_session_factory,
        username="admin",
        full_name="Admin User",
        password="another-password",
    )

    async with postgres_session_factory() as session:
        admin_count = await session.scalar(select(func.count()).select_from(User))

    assert first.created is True
    assert first.temporary_password is None
    assert second.created is False
    assert second.temporary_password is None
    assert first.user.id == second.user.id
    assert admin_count == 1


@pytest.mark.asyncio
async def test_seed_e2e_admin_is_idempotent_and_does_not_return_password(
    postgres_session_factory: async_sessionmaker,
) -> None:
    first = await seed_e2e_admin(
        session_factory=postgres_session_factory,
        username="e2e-admin",
        full_name="E2E Admin",
        password="first-password",
    )
    second = await seed_e2e_admin(
        session_factory=postgres_session_factory,
        username="e2e-admin",
        full_name="E2E Admin Updated",
        password="second-password",
    )

    async with postgres_session_factory() as session:
        admin = await session.scalar(select(User).where(User.username == "e2e-admin"))

    assert first.id == second.id
    assert admin is not None
    assert admin.full_name == "E2E Admin Updated"
    assert admin.role == UserRole.ADMIN
    assert admin.is_active is True
    assert PasswordHash.recommended().verify("second-password", admin.password_hash)


@pytest.mark.asyncio
async def test_seed_e2e_operator_is_idempotent_and_does_not_return_password(
    postgres_session_factory: async_sessionmaker,
) -> None:
    first = await seed_e2e_operator(
        session_factory=postgres_session_factory,
        username="e2e-operator",
        full_name="E2E Operator",
        password="first-password",
    )
    second = await seed_e2e_operator(
        session_factory=postgres_session_factory,
        username="e2e-operator",
        full_name="E2E Operator Updated",
        password="second-password",
    )

    async with postgres_session_factory() as session:
        operator = await session.scalar(select(User).where(User.username == "e2e-operator"))

    assert first.id == second.id
    assert operator is not None
    assert operator.full_name == "E2E Operator Updated"
    assert operator.role == UserRole.OPERATOR
    assert operator.is_active is True
    assert PasswordHash.recommended().verify("second-password", operator.password_hash)
