from uuid import uuid4

from app.models import OperatorError, OperatorErrorSource, OperatorErrorType, TrainingResult
from app.services.skill_profile import build_skill_values


def test_build_skill_values_is_explainable_and_idempotent() -> None:
    session_id = uuid4()
    result = TrainingResult(
        session_id=session_id,
        scenario_id=uuid4(),
        score=80.0,
        max_score=100.0,
        reaction_time_ms=7000,
        error_count=2,
        critical_error_count=0,
        sequence_score=75.0,
        reaction_score=80.0,
        safety_score=100.0,
        status="final",
        summary={},
    )
    errors = [
        OperatorError(
            session_id=session_id,
            error_type=OperatorErrorType.WRONG_ACTION,
            severity="warning",
            source=OperatorErrorSource.RULE,
            evidence={"actual": {"equipment_id": "FRC404"}},
            causal_chain=[],
        ),
        OperatorError(
            session_id=session_id,
            error_type=OperatorErrorType.LATE_ACTION,
            severity="warning",
            source=OperatorErrorSource.RULE,
            evidence={"actual": {"equipment_id": "H1A"}},
            causal_chain=[],
        ),
    ]

    values = build_skill_values([result], errors)

    assert values["procedure_sequence"] == (75.0, 1)
    assert values["reaction_speed"] == (80.0, 1)
    assert values["regulation"] == (80.0, 1)
    assert values["pump_control"] == (90.0, 1)
    assert values["alarm_handling"] == (0.0, 0)


def test_build_skill_values_accepts_error_types_loaded_as_strings() -> None:
    session_id = uuid4()
    result = TrainingResult(
        session_id=session_id,
        scenario_id=uuid4(),
        score=80.0,
        max_score=100.0,
        reaction_time_ms=7000,
        error_count=1,
        critical_error_count=0,
        sequence_score=90.0,
        reaction_score=90.0,
        safety_score=100.0,
        status="final",
        summary={},
    )
    error = OperatorError(
        session_id=session_id,
        error_type=OperatorErrorType.WRONG_ACTION,
        severity="warning",
        source=OperatorErrorSource.RULE,
        evidence={"actual": {"equipment_id": "FRC404"}},
        causal_chain=[],
    )
    # PostgreSQL String columns are returned as str despite the ORM annotation.
    error.error_type = OperatorErrorType.WRONG_ACTION.value  # type: ignore[assignment]

    values = build_skill_values([result], [error])

    assert values["regulation"] == (80.0, 1)
