from uuid import UUID

from app.models import OperatorErrorType
from app.services.training_insights import SkillProfile, build_recommendations


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
        weakest_skill="sequence",
        recent_scores=[70.0, 74.0, 72.0],
    )

    recommendations = build_recommendations(profile)

    assert [item.focus for item in recommendations] == ["sequence", "reaction_time"]
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
