import asyncio
from uuid import uuid4

from app.config import LLMSettings
from app.explanation.service import NarrativeService
from app.schemas.contracts import DebriefRequest, ErrorExplanationRequest


class FakeLLMClient:
    async def complete_json(self, *, system_prompt: str, payload: dict[str, object]) -> dict[str, object]:
        if "error_code" in payload:
            return {
                "summary": "Поздняя реакция",
                "explanation": "Действие выполнено позже допустимого окна, указанного во входных фактах.",
                "recommendation": "Повторить шаг с контролем времени реакции.",
            }
        return {
            "short_summary": "Сессия завершена с одной ошибкой реакции.",
            "strengths": ["Последовательность сохранена."],
            "weaknesses": ["LATE_ACTION"],
            "priority_actions": ["Отработать скорость реакции."],
            "recommended_scenario_code": None,
        }


def settings(mode: str) -> LLMSettings:
    return LLMSettings(
        mode=mode,
        base_url="http://llm/v1",
        model="test-model",
        api_key=None,
        timeout_seconds=1.0,
        temperature=0.0,
    )


def test_disabled_llm_uses_deterministic_fallback() -> None:
    service = NarrativeService(settings("disabled"), FakeLLMClient())  # type: ignore[arg-type]
    result = asyncio.run(
        service.explain_error(ErrorExplanationRequest(error_code="LATE_ACTION", severity="warning"))
    )
    assert result.model == "rules-fallback-v1"
    assert "LATE_ACTION" in result.summary


def test_openai_compatible_mode_returns_validated_llm_narrative() -> None:
    service = NarrativeService(settings("openai_compatible"), FakeLLMClient())  # type: ignore[arg-type]
    explanation = asyncio.run(
        service.explain_error(ErrorExplanationRequest(error_code="LATE_ACTION", severity="warning"))
    )
    debrief = asyncio.run(
        service.build_debrief(
            DebriefRequest(
                session_id=uuid4(),
                session_result={"score": 90},
                errors=[],
            )
        )
    )
    assert explanation.model == "llm:test-model"
    assert explanation.sources == []
    assert debrief.model == "llm:test-model"
    assert debrief.recommended_scenario_code is None
