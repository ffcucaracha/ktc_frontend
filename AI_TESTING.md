# Тестирование AI-контура MVP

Этот файл фиксирует проверяемые свойства AI-интеграции и команды для локального прогона.
Физическая модель `ktc_backend` остаётся отдельным источником authoritative process state; тесты AI
не должны подменять её собственной технологической логикой.

## Backend

Уже существующие тесты повторно не дублируются:

- `backend/tests/integration/test_simulation_timeline.py` проверяет порядок timeline и отсутствие
  дублирования `state.snapshot` для одной revision;
- `backend/tests/test_ai_gateway_contract.py` проверяет HTTP-контракт AI и отдельный короткий timeout
  realtime prediction;
- `backend/tests/test_skill_profile.py` и `backend/tests/test_training_insights.py` проверяют профиль
  компетенций и правила рекомендаций;
- тесты feature engineering и dataset находятся в `ai-service/tests/`.

На этапе 14 добавлены недостающие проверки:

- `test_training_assessment.py` — одна и та же последовательность действий детерминированно даёт
  `WRONG_SEQUENCE`, одинаковый балл и не накапливает повторные ошибки при пересчёте;
- `test_command_durability.py` — pending-команда и `operator.command` уже видны в другой DB-сессии до
  вызова внешнего simulation gateway;
- `test_training_api.py` — оператор не читает чужой timeline, активный `exam` не отдаёт debrief, после
  завершения экзамена debrief доступен;
- `test_ai_fail_open.py` — timeout AI не останавливает сбор телеметрии и активную simulation session,
  а ошибка фиксируется как `integration.error` с `source=ai`.

PostgreSQL integration tests намеренно требуют явного флага:

```bash
cd backend
RUN_POSTGRES_TESTS=1 pytest
```

Обычные backend unit/contract tests:

```bash
cd backend
pytest
ruff check app tests
mypy app
```

## AI-service

```bash
cd ai-service
pytest
```

Проверяются контракт API, feature engineering без утечки будущего, генерация dataset, поведение
predictor без модели и LLM deterministic fallback.

## Frontend

На этапе 14 добавлены component tests:

- `AiCoachPanel` показывает realtime risk и fail-open состояние `AI недоступен`;
- `OilHeatingSimulator` показывает AI coach только в `training` и скрывает его в `exam`;
- `OperatorSessionResultPage` показывает фактическую ошибку вместе с более ранним ML prediction;
- `OperatorSkillProfile` и `TrainingTimeline` отображают профиль навыков и визуально различают
  prediction / actual error.

Запуск:

```bash
cd frontend
npm test
npm run typecheck
npm run lint
```

## E2E

`frontend/e2e/mvp.spec.ts` проходит основной пользовательский путь:

```text
admin creates operator
→ operator logs in
→ starts scenario
→ performs an intentionally wrong action
→ finishes session
→ opens final assessment/debrief
→ sees error analysis and next-training recommendation
```

Запуск после старта docker compose:

```bash
cd frontend
npm run e2e
```

Отдельный E2E assert на ненулевое ML-предупреждение не должен зависеть от случайного результата модели.
Пока в репозитории нет обученного `risk-catboost-v1.cbm`, realtime warning проверяется детерминированным
component test с зафиксированным prediction payload. После появления versioned demo-модели можно
добавить отдельный Playwright smoke-тест на `risk >= threshold`, не меняя production-код.

## Что считается критическим regression

- AI timeout блокирует simulation command или прекращает сбор authoritative telemetry;
- operator получает доступ к чужой тренировке;
- active exam показывает AI hint/debrief;
- повторная assessment-обработка меняет результат без изменения timeline;
- prediction визуально выдаётся за фактическую ошибку или меняет process state;
- в логах появляются пароли, JWT/refresh tokens или `AI_LLM_API_KEY`.
