# MVP readiness

Итоговый чек-лист вертикального AI-контура после этапов интеграции.

## Кодовый контур

### Готово

- server-side telemetry collection независимо от frontend polling;
- timeline `SimulationEvent` с snapshots, operator commands, result events и AI audit;
- учебные сценарии и режимы `training` / `exam`;
- deterministic assessment и классификация ошибок;
- `TrainingResult` и `OperatorError`;
- post-session event processing с retry/idempotency;
- persistent `OperatorSkillProfile`;
- персональные рекомендации;
- deterministic выбор конкретного следующего scenario code из активных сценариев;
- realtime ML risk contract и WebSocket delivery;
- AI Coach в training и скрытие hints в active exam;
- result/debrief page с ML prediction и actual error на одной шкале;
- admin training analytics;
- OpenAI-compatible LLM explanation/debrief с fallback;
- AI fail-open и отдельный prediction timeout;
- AI audit;
- Docker/env configuration;
- backend/frontend/E2E test coverage для критических свойств;
- exporter `DB → session_exports.jsonl`;
- dataset generator и CatBoost training script.

## Полный демонстрационный цикл

После установки реальной модели система поддерживает цепочку:

```text
1. оператор выбирает сценарий
2. digital twin выдаёт authoritative telemetry
3. backend независимо сохраняет telemetry и действия
4. ML оценивает risk в ближайшие 10 секунд
5. prediction сохраняется в timeline и показывается AI Coach в training
6. оператор совершает/не совершает ожидаемое действие
7. rules engine фиксирует фактическую ошибку
8. session.completed запускает final assessment
9. skill profile пересчитывается
10. backend выбирает следующий активный сценарий
11. operator получает debrief и кнопку перехода к рекомендованной тренировке
12. admin видит историю, динамику и skill profile
```

## Что нельзя считать завершённым только кодом

### 1. Обученная ML-модель

В Git намеренно нет готового `risk-catboost-v1.cbm`.

Для реального prediction требуется:

```text
накопить сессии цифрового двойника
→ экспортировать JSONL
→ построить dataset
→ проверить классы/leakage
→ обучить CatBoost
→ оценить качество и threshold
→ положить .cbm + metadata в ai-service/models
```

Инструкция: `ai-service/ML_RISK_MODEL_RUNBOOK.md`.

### 2. Проверка реального telemetry contract

До обучения нужно подтвердить на актуальном `ktc_backend`:

- наличие и смысл `PRA351`;
- наличие и смысл `TR41_1`;
- единицы измерения;
- формат pump/regulator state;
- корректность `simulation_time_ms` и `revision`;
- какие alarms реально доступны в текущей модели.

Без этой сверки обучать production-like модель нельзя.

### 3. Фактический test run

Тесты добавлены в репозиторий, но их нужно реально прогнать на целевой машине:

```bash
cd backend
pytest
RUN_POSTGRES_TESTS=1 pytest
ruff check app tests
mypy app

cd ../ai-service
pytest

cd ../frontend
npm test
npm run typecheck
npm run lint
npm run build
npm run e2e
```

До фактического прогона нельзя утверждать, что весь suite зелёный.

### 4. LLM для демонстрации

LLM не обязательна для работоспособности MVP: deterministic fallback уже существует.

Если на защите требуется показать LLM-разбор, заранее поднять/проверить OpenAI-compatible endpoint и выставить:

```env
AI_GATEWAY_MODE=http
AI_LLM_MODE=openai_compatible
```

## RAG

RAG сознательно находится **после MVP**.

Архитектурная точка расширения уже есть (`RAG_ENABLED`, source references в contracts/audit), но retrieval pipeline не реализован.

Следующий этап:

```text
регламенты
→ chunks
→ embeddings
→ vector store
→ retrieval
→ explanation с source_id / разделом / страницей
```

Это улучшит доказуемость объяснений, но не должно менять authoritative process logic и deterministic assessment.

## Критерий готовности к защите

Перед демонстрацией должны быть подтверждены четыре пункта:

1. `docker compose up --build` поднимает стенд на целевой машине;
2. полный test suite фактически прогнан;
3. `ktc_backend` отдаёт ожидаемый telemetry contract;
4. обученная demo ML-модель выдаёт воспроизводимый ненулевой risk на заранее подготовленном сценарии.

Если пункт 4 ещё не выполнен, систему можно демонстрировать как полностью собранный ML pipeline с `risk-model-unavailable`, но нельзя заявлять, что реальная модель уже обучена и прогнозирует ошибки.
