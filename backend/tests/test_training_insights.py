from uuid import UUID, uuid4

from app.models import OperatorError, OperatorErrorSource, OperatorErrorType, TrainingResult
from app.services.training_insights import SkillProfile, build_recommendations, build_skill_profile


def test_recommendations_prioritize_sequence_and_reaction_errors() -> None:
    profile = SkillProfile(
        operator_id=UUID("11111111-1111-1111-1111-111111111111"),
        assessed_sessions=3,
        average_score=72.0,
        average_sequence_score=60.0,
        average_reaction_score=65.0,
        average_safety_score=100.0,
        error_counts={
            OperatorErrorType.WRONG_SEQUENCE.value: 2,
            OperatorErrorType.LATE_ACTION.value: 1,
        },
        weakest_skill="procedure_sequence",
        recent_scores=[70.0, 74.0, 72.0],
    )

    recommendations = build_recommendations(profile)

    assert [item.focus for item in recommendations] == ["procedure_sequence", "reaction_speed"]
    assert [item.priority for item in recommendations] == [1, 2]


def test_recommendations_provide_baseline_for_new_operator() -> None:
    profile = SkillProfile(
        operator_id=UUID("22222222-2222-2222-2222-222222222222"),
        assessed_sessions=0,
        average_score=None,
        average_sequence_score=None,
        average_reaction_score=None,
        average_safety_score=None,
        error_counts={},
        weakest_skill=None,
        recent_scores=[],
    )

    recommendations = build_recommendations(profile)

    assert len(recommendations) == 1
    assert recommendations[0].focus == "baseline"


def test_skill_profile_aggregates_error_type_loaded_as_string() -> None:
    operator_id = uuid4()
    session_id = uuid4()
    result = TrainingResult(
        session_id=session_id,
        scenario_id=uuid4(),
        score=85.0,
        max_score=100.0,
        reaction_time_ms=2000,
        error_count=1,
        critical_error_count=0,
        sequence_score=80.0,
        reaction_score=90.0,
        safety_score=100.0,
        status="final",
        summary={},
    )
    error = OperatorError(
        session_id=session_id,
        error_type=OperatorErrorType.WRONG_SEQUENCE,
        severity="warning",
        source=OperatorErrorSource.RULE,
        evidence={},
        causal_chain=[],
    )
    error.error_type = OperatorErrorType.WRONG_SEQUENCE.value  # type: ignore[assignment]

    profile = build_skill_profile(operator_id, [result], [error])

    assert profile.error_counts == {OperatorErrorType.WRONG_SEQUENCE.value: 1}
