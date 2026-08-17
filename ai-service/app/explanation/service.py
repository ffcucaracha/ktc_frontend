from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.config import LLMSettings, load_llm_settings
from app.llm.client import LLMClientError, OpenAICompatibleLLMClient
from app.schemas.contracts import (
    Debrief,
    DebriefRequest,
    ErrorExplanation,
    ErrorExplanationRequest,
)

ERROR_SYSTEM_PROMPT = """Ты — модуль объяснения ошибок оператора промышленного тренажёра.
Используй только факты из входного JSON. Не меняй error_code, severity, итоговую оценку и факты assessment.
Не придумывай технологические регламенты, причины, последствия или параметры, которых нет во входе.
Не давай команды реальной установке. Сформируй короткое учебное объяснение на русском языке.
Верни только JSON с полями summary, explanation, recommendation.
"""

DEBRIEF_SYSTEM_PROMPT = """Ты — учебный AI-инструктор промышленного тренажёра.
Сформируй краткий персональный разбор завершённой сессии только по переданным структурированным фактам.
Нельзя менять итоговый балл, типы ошибок, severity и результаты deterministic assessment.
Не придумывай отсутствующие технологические требования или факты. Не предлагай управление реальной установкой.
Верни только JSON с полями short_summary, strengths, weaknesses, priority_actions, recommended_scenario_code.
recommended_scenario_code может быть null, если выбор конкретного сценария не следует из входных данных.
"""


class NarrativeService:
    def __init__(
        self,
        settings: LLMSettings | None = None,
        client: OpenAICompatibleLLMClient | None = None,
    ) -> None:
        self._settings = settings or load_llm_settings()
        self._client = client or OpenAICompatibleLLMClient(self._settings)

    async def explain_error(self, request: ErrorExplanationRequest) -> ErrorExplanation:
        fallback = _fallback_error_explanation(request)
        if self._settings.mode != "openai_compatible":
            return fallback
        try:
            payload = await self._client.complete_json(
                system_prompt=ERROR_SYSTEM_PROMPT,
                payload=request.model_dump(mode="json"),
            )
            return ErrorExplanation(
                summary=str(payload["summary"]),
                explanation=str(payload["explanation"]),
                recommendation=str(payload["recommendation"]),
                # RAG is intentionally outside the MVP. Sources remain empty unless explicit
                # regulation_context was supplied by another trusted backend component.
                sources=request.regulation_context,
                model=f"llm:{self._settings.model}",
            )
        except (LLMClientError, KeyError, TypeError, ValidationError):
            return fallback

    async def build_debrief(self, request: DebriefRequest) -> Debrief:
        fallback = _fallback_debrief(request)
        if self._settings.mode != "openai_compatible":
            return fallback
        try:
            payload = await self._client.complete_json(
                system_prompt=DEBRIEF_SYSTEM_PROMPT,
                payload=request.model_dump(mode="json"),
            )
            return Debrief(
                short_summary=str(payload["short_summary"]),
                strengths=_string_list(payload.get("strengths")),
                weaknesses=_string_list(payload.get("weaknesses")),
                priority_actions=_string_list(payload.get("priority_actions")),
                recommended_scenario_code=(
                    payload.get("recommended_scenario_code")
                    if isinstance(payload.get("recommended_scenario_code"), str)
                    else None
                ),
                model=f"llm:{self._settings.model}",
            )
        except (LLMClientError, KeyError, TypeError, ValidationError):
            return fallback


def _fallback_error_explanation(request: ErrorExplanationRequest) -> ErrorExplanation:
    evidence = request.actual_action or request.process_context
    detail = " Структурированный контекст сохранён для повторного разбора." if evidence else ""
    return ErrorExplanation(
        summary=f"Зафиксирована ошибка {request.error_code}.",
        explanation=(
            "Ошибка определена детерминированным assessment-контуром; AI не меняет её классификацию."
            + detail
        ),
        recommendation="Повторите соответствующий шаг учебного сценария и сверяйтесь с его последовательностью.",
        sources=request.regulation_context,
        model="rules-fallback-v1",
    )


def _fallback_debrief(request: DebriefRequest) -> Debrief:
    score = request.session_result.get("score")
    weaknesses = list(dict.fromkeys(item.error_code for item in request.errors))
    return Debrief(
        short_summary=(
            f"Результат тренировки: {score}." if score is not None else "Тренировка завершена."
        ),
        strengths=[] if weaknesses else ["Классифицированные ошибки отсутствуют."],
        weaknesses=weaknesses,
        priority_actions=[f"Повторить работу с ошибкой {code}." for code in weaknesses[:3]],
        recommended_scenario_code=None,
        model="rules-fallback-v1",
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


narrative_service = NarrativeService()
