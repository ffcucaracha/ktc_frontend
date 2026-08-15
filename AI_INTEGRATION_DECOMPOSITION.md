# Полная декомпозиция интеграции ИИ

## 1. Цель

Добавить в существующий компьютерный тренажёр интеллектуальный контур, который:

- сохраняет полную историю тренировки;
- выявляет и классифицирует ошибки оператора;
- оценивает квалификацию по результатам сессии;
- прогнозирует риск ошибки до её совершения;
- формирует персональный разбор и рекомендации;
- подбирает следующий сценарий обучения;
- при необходимости объясняет результат через LLM/RAG, не передавая LLM право определять физическую корректность процесса.

Ключевой архитектурный принцип: `ktc_backend` остаётся источником истины по технологическому процессу и физической модели. Наш FastAPI backend остаётся источником истины по пользователю, тренировочной сессии, командам и оценке. AI работает сбоку как аналитический контур и не управляет установкой напрямую.

---

## 2. Текущая архитектура и точка интеграции

Сейчас цепочка выглядит так:

```text
React frontend
    ↓ REST / polling / WebSocket
FastAPI application backend
    ↓
SimulationService
    ↓
SimulationGateway
    ↓
KtcOilHeatingGateway
    ↓
ktc_backend
```

ИИ следует подключать к application backend, а не к `ktc_backend` и не напрямую к React.

Основные существующие точки расширения:

```text
backend/app/services/simulation.py
backend/app/integrations/simulation/
backend/app/models/
backend/app/repositories/
backend/app/api/v1/endpoints/simulation.py
frontend/src/entities/simulation/
frontend/src/widgets/oil-heating-simulator/
frontend/src/pages/admin-operator-detail/
```

---

# Этап 1. Полный timeline тренировочной сессии

## 3. Новая сущность `SimulationEvent`

### Новый файл

```text
backend/app/models/simulation_event.py
```

### Поля

```text
id UUID PK
session_id UUID FK -> simulation_sessions.id
event_type string / enum
source string / enum
revision int nullable
simulation_time_ms bigint nullable
payload JSONB
created_at timestamptz
```

Рекомендуемые `event_type`:

```text
session.started
state.snapshot
operator.command
command.accepted
command.rejected
alarm.raised
alarm.cleared
session.completed
session.failed
```

Рекомендуемый `source`:

```text
operator
simulation
system
assessment
ai
```

Индексы:

```text
(session_id, created_at)
(session_id, simulation_time_ms)
(session_id, event_type)
```

Не удалять `SimulationSession.last_state`: он остаётся быстрым текущим snapshot для UI. `SimulationEvent` нужен как неизменяемая история.

## 4. Миграция

### Новый файл

```text
backend/alembic/versions/<date>_add_simulation_events.py
```

Добавить таблицу `simulation_events`, FK с каскадным удалением либо явной политикой хранения.

## 5. Репозиторий событий

### Новый файл

```text
backend/app/repositories/simulation_events.py
```

Методы:

```python
create_event(...)
create_state_snapshot(...)
create_operator_command_event(...)
list_for_session(...)
list_recent_for_session(...)
list_between_simulation_times(...)
```

Для больших объёмов предусмотреть batch insert, но для MVP достаточно обычной записи.

## 6. Изменения `SimulationService`

### Файл

```text
backend/app/services/simulation.py
```

Добавить `SimulationEventRepository` в конструктор.

### `create_session()`

После успешного запуска локальной/внешней сессии сохранить:

```text
session.started
```

Если внешний сервис вернул initial state, сохранить его и в `last_state`, и как `state.snapshot`.

### `get_state()`

Сейчас метод только обновляет `last_state`. После получения нового состояния:

1. проверить revision;
2. обновить `last_state`;
3. сохранить `state.snapshot` в `simulation_events`;
4. не создавать дубликат, если revision уже сохранён.

Нужна идемпотентность по паре:

```text
session_id + revision + event_type
```

### `send_command()`

После создания `SimulationCommand` сохранить отдельный `operator.command` event с:

```json
{
  "command_id": "...",
  "equipment_id": "H1A",
  "action": "start",
  "payload": {},
  "expected_revision": 12
}
```

Очень важно: событие должно фиксироваться до обращения к `ktc_backend`, потому что оно описывает фактическое действие/намерение оператора.

После ответа внешнего сервиса сохранить:

```text
command.accepted
```

или:

```text
command.rejected
```

### `apply_event()`

Каждое нормализованное событие от `SimulationGateway` также сохранять в `simulation_events` до/вместе с применением к `SimulationSession`.

### `stop_session()`

Сохранять `session.completed` или `session.failed`.

---

# Этап 2. Server-side сбор телеметрии

## 7. Почему нельзя опираться только на React polling

Сейчас `OilHeatingRuntime` запрашивает snapshot примерно раз в 2 секунды. Для UI этого достаточно, но для обучающей истории это ненадёжно: вкладка может быть закрыта, браузер — уснуть, сеть — пропасть.

Историю обучения должен собирать backend независимо от клиента.

## 8. Новый сервис `SimulationTelemetryCollector`

### Новый файл

```text
backend/app/services/simulation_telemetry.py
```

Ответственность:

- пока сессия `ACTIVE`, периодически получать состояние через `SimulationGateway.get_state()`;
- сохранять только новые revision;
- обновлять `last_state`;
- писать `state.snapshot` в timeline;
- прекращать polling после завершения/ошибки сессии.

Для MVP допустим интервал 1–2 секунды.

### Запуск

Варианты:

1. MVP: `asyncio.Task` на активную сессию внутри FastAPI process;
2. production: отдельный worker / task queue.

В документации сразу указать, что вариант 1 демонстрационный, а для горизонтального масштабирования collector выносится в worker.

---

# Этап 3. Сценарии обучения

## 9. Новая сущность `TrainingScenario`

### Новый файл

```text
backend/app/models/training_scenario.py
```

Поля:

```text
id UUID
code string unique
simulator_definition_id UUID
name string
description text
difficulty enum/basic|medium|advanced
is_active boolean
config JSONB
created_at
updated_at
```

`config` должен позволять хранить сценарную конфигурацию без зашивания всех сценариев в Python-код.

## 10. Сущность `ScenarioExpectedAction`

### Новый файл

```text
backend/app/models/scenario_expected_action.py
```

Поля:

```text
id UUID
scenario_id UUID
step_code string
equipment_id string
action string
payload_constraints JSONB nullable
condition JSONB
allowed_delay_ms int nullable
severity_if_missed string
order_index int
```

Для MVP допустимо часть логики хранить в Python rule classes, а в БД — метаданные и параметры.

## 11. Связь сценария с сессией

Расширить `SimulationSession`:

```text
training_scenario_id UUID nullable
mode training | exam
```

### Изменить

```text
backend/app/models/simulation_session.py
backend/app/schemas/simulation.py
backend/app/api/v1/endpoints/simulation.py
frontend/src/entities/simulation/api/types.ts
```

При создании сессии frontend должен передавать:

```json
{
  "simulator_id": "...",
  "scenario_id": "...",
  "mode": "training"
}
```

---

# Этап 4. Ошибки и оценивание

## 12. Новая сущность `OperatorError`

### Новый файл

```text
backend/app/models/operator_error.py
```

Поля:

```text
id UUID
session_id UUID
scenario_id UUID nullable
error_code string
category string
severity info|warning|critical
equipment_id string nullable
started_at_ms bigint nullable
detected_at_ms bigint nullable
resolved_at_ms bigint nullable
actual_action JSONB nullable
expected_action JSONB nullable
context JSONB
cause JSONB nullable
consequences JSONB nullable
detection_source rule|ml|hybrid
confidence numeric nullable
created_at
```

Примеры `error_code`:

```text
LATE_ACTION
WRONG_EQUIPMENT
WRONG_ACTION
WRONG_SEQUENCE
MISSED_ALARM
INVALID_SETPOINT
UNNECESSARY_ACTION
```

## 13. Новый `AssessmentService`

### Новый файл

```text
backend/app/services/assessment.py
```

Ответственность:

- читать timeline сессии;
- сравнивать действия с правилами сценария;
- классифицировать ошибки;
- вычислять время реакции;
- строить причинно-следственный контекст;
- записывать `OperatorError`;
- считать итоговую оценку.

Не использовать LLM как источник истины при определении ошибки.

## 14. Rules Engine

### Новая директория

```text
backend/app/assessment/
    __init__.py
    base.py
    engine.py
    rules/
        oil_heating.py
```

Базовый интерфейс:

```python
class AssessmentRule(Protocol):
    def evaluate(self, context: AssessmentContext) -> list[DetectedError]: ...
```

`AssessmentContext` включает:

```text
scenario
recent states
recent commands
active alarms
current state
simulation time
```

Для MVP достаточно 4–6 хорошо демонстрируемых типов ошибок.

## 15. Новая сущность `TrainingResult`

### Новый файл

```text
backend/app/models/training_result.py
```

Поля:

```text
id UUID
session_id UUID unique
operator_id UUID
scenario_id UUID nullable
score numeric
status passed|failed
reaction_time_avg_ms bigint nullable
errors_total int
critical_errors int
summary JSONB
created_at
```

Итоговый `summary` может содержать breakdown по категориям навыков.

## 16. Завершение сессии

При `stop_session()` или `session.completed`:

1. закрыть сбор telemetry;
2. запустить финальный assessment;
3. сформировать `TrainingResult`;
4. сохранить итог;
5. затем асинхронно запросить AI debrief.

---

# Этап 5. API результатов и ошибок

## 17. Новые endpoints в application backend

### Новый файл

```text
backend/app/api/v1/endpoints/training.py
```

Endpoints для оператора:

```text
GET /api/v1/simulation-sessions/{session_id}/assessment
GET /api/v1/simulation-sessions/{session_id}/errors
GET /api/v1/simulation-sessions/{session_id}/timeline
GET /api/v1/simulation-sessions/{session_id}/debrief
```

Endpoints для администратора:

```text
GET /api/v1/operators/{operator_id}/training-results
GET /api/v1/operators/{operator_id}/skill-profile
GET /api/v1/operators/{operator_id}/recommendations
```

Права:

- оператор видит только собственные результаты;
- admin видит результаты всех операторов;
- режим `exam` не отдаёт подсказки во время активной сессии.

---

# Этап 6. Контракт FastAPI ↔ AI-service

## 18. Новый отдельный сервис

Рекомендуемая директория на первом этапе:

```text
ai-service/
    pyproject.toml
    Dockerfile
    app/
        main.py
        api/
        schemas/
        features/
        prediction/
        explanation/
        recommendations/
        rag/
    models/
    tests/
```

Если команда хочет держать AI в отдельном репозитории, в текущем monorepo оставить только контракт и gateway.

## 19. Gateway в текущем backend

### Новая директория

```text
backend/app/integrations/ai/
    __init__.py
    base.py
    dto.py
    http_gateway.py
    mock_gateway.py
    factory.py
    errors.py
```

Интерфейс:

```python
class AIGateway(Protocol):
    async def predict_risk(self, request: RiskPredictionRequest) -> RiskPrediction: ...
    async def explain_error(self, request: ErrorExplanationRequest) -> ErrorExplanation: ...
    async def build_debrief(self, request: DebriefRequest) -> Debrief: ...
    async def recommend_training(self, request: RecommendationRequest) -> Recommendation: ...
```

## 20. Контракт `POST /v1/predict-risk`

Request:

```json
{
  "session_id": "uuid",
  "scenario_code": "oil-heating-pressure-rise",
  "operator_profile": {
    "previous_errors": {
      "LATE_ACTION": 3
    }
  },
  "window": [
    {
      "simulation_time_ms": 10000,
      "revision": 10,
      "sensors": {
        "TR41_1": 118.2,
        "PRA351": 4.6
      },
      "pumps": {
        "H1A": true,
        "H1B": false,
        "H1V": true
      },
      "regulators": {
        "FRC404": 35
      }
    }
  ],
  "recent_actions": [
    {
      "simulation_time_ms": 8000,
      "equipment_id": "FRC404",
      "action": "set",
      "payload": {"value": 35}
    }
  ]
}
```

Response:

```json
{
  "risk": 0.84,
  "predicted_error_code": "LATE_ACTION",
  "horizon_seconds": 10,
  "model_version": "risk-catboost-v1",
  "features": [
    {"name": "pressure_delta_10s", "importance": 0.31},
    {"name": "time_since_alarm", "importance": 0.22}
  ]
}
```

## 21. Контракт `POST /v1/explain-error`

Request должен содержать уже определённую ошибку и факты:

```json
{
  "error_code": "WRONG_SEQUENCE",
  "severity": "critical",
  "expected_action": {...},
  "actual_action": {...},
  "process_context": {...},
  "cause": [...],
  "consequences": [...],
  "regulation_context": [...]
}
```

Response:

```json
{
  "summary": "...",
  "explanation": "...",
  "recommendation": "...",
  "sources": [...],
  "model": "..."
}
```

LLM не должен придумывать `error_code`, причины или фактические значения датчиков. Он только объясняет переданные структурированные факты.

## 22. Контракт `POST /v1/debrief`

Request:

```text
session result
errors
reaction metrics
operator skill profile
scenario metadata
```

Response:

```text
short_summary
strengths[]
weaknesses[]
priority_actions[]
recommended_scenario_code
```

---

# Этап 7. ML-прогноз риска

## 23. Feature engineering

### `ai-service/app/features/`

Минимальный набор признаков:

```text
current pressure
pressure_delta_5s
pressure_delta_10s
current temperature
temperature_delta_10s
pump states
regulator values
number_of_active_alarms
time_since_alarm
time_since_last_action
action_count_last_10s
scenario_step
previous_error_count by category
```

Важно строить признаки только из информации, доступной до прогнозируемой ошибки, чтобы не допустить data leakage.

## 24. Модель

Для MVP рекомендуется CatBoost/градиентный бустинг по табличным признакам.

Первый target:

```text
ERROR_IN_NEXT_10_SECONDS = 0/1
```

После MVP — multiclass:

```text
NO_ERROR
LATE_ACTION
WRONG_ACTION
WRONG_SEQUENCE
MISSED_ALARM
INVALID_SETPOINT
```

## 25. Синтетический dataset

Использовать цифровой двойник для генерации траекторий:

```text
эталонный сценарий
+ задержка действия
+ пропуск действия
+ неверный насос
+ неверный регулятор
+ неверное значение setpoint
+ неправильный порядок
```

Сохранять dataset с явным происхождением данных и версией сценария.

### Новая директория

```text
ai-service/datasets/
ai-service/scripts/generate_dataset.py
ai-service/scripts/train_risk_model.py
```

Не коммитить большие datasets и бинарные модели без необходимости; хранить инструкции воспроизводимости.

---

# Этап 8. Профиль навыков и персонализация

## 26. Новая сущность `OperatorSkillProfile`

### Новый файл

```text
backend/app/models/operator_skill_profile.py
```

Вариант полей:

```text
id UUID
operator_id UUID
skill_code string
score numeric
sample_count int
updated_at
```

Навыки для MVP:

```text
pump_control
regulation
alarm_handling
reaction_speed
procedure_sequence
emergency_response
```

## 27. `SkillProfileService`

### Новый файл

```text
backend/app/services/skill_profile.py
```

После каждой завершённой тренировки:

1. взять `TrainingResult` и ошибки;
2. обновить оценки компетенций;
3. сохранить профиль;
4. запросить рекомендованный сценарий.

Персонализация должна быть объяснимой: рекомендация должна содержать причину, например «3 из 4 последних критических ошибок связаны с поздней реакцией на рост давления».

---

# Этап 9. Frontend — оператор

## 28. Новая entity `training`

### Новая директория

```text
frontend/src/entities/training/
    api/
        trainingApi.ts
        types.ts
    model/
        queries.ts
    lib/
        format.ts
```

Типы:

```text
OperatorError
TrainingAssessment
TrainingResult
RiskPrediction
AICoachMessage
SessionDebrief
```

## 29. `AiCoachPanel`

### Новый компонент

```text
frontend/src/widgets/ai-coach/AiCoachPanel.tsx
```

Показывает во время `training`:

- текущий уровень риска;
- прогнозируемый тип ошибки;
- краткую причину;
- предупреждение/рекомендацию;
- время обновления;
- состояние «AI недоступен» без остановки тренажёра.

Не блокирует управление установкой.

## 30. Интеграция в `OilHeatingSimulator`

### Изменить

```text
frontend/src/widgets/oil-heating-simulator/OilHeatingSimulator.tsx
```

Добавить справа/снизу `AiCoachPanel`.

В режиме:

```text
training -> показывать prediction/hints
exam -> не показывать prediction/hints, только собирать их на backend
```

## 31. WebSocket события AI

Расширить:

```text
frontend/src/entities/simulation/api/types.ts
```

Новыми событиями:

```text
assessment.error.detected
ai.risk.updated
ai.explanation.ready
training.result.ready
```

Пример:

```json
{
  "type": "ai.risk.updated",
  "data": {
    "risk": 0.84,
    "predicted_error_code": "LATE_ACTION",
    "horizon_seconds": 10
  }
}
```

AI-события не должны менять authoritative process state.

---

# Этап 10. Frontend — итоговый разбор

## 32. Новая страница

```text
frontend/src/pages/operator-session-result/OperatorSessionResultPage.tsx
```

Разделы:

```text
Итоговая оценка
Количество ошибок
Критические ошибки
Среднее время реакции
Timeline ключевых событий
Ошибки с объяснениями
AI Debrief
Рекомендованная следующая тренировка
```

После `stopSimulationSession` вместо немедленного возврата в каталог можно переходить на:

```text
/operator/sessions/{sessionId}/result
```

## 33. Timeline component

```text
frontend/src/widgets/training-timeline/TrainingTimeline.tsx
```

Показывает синхронно:

```text
alarm
operator action
state change
error detection
risk prediction
```

Для демонстрации жюри особенно важно визуально показать, что прогноз появился раньше фактической ошибки.

---

# Этап 11. Frontend — администратор

## 34. Расширить карточку оператора

### Изменить

```text
frontend/src/pages/admin-operator-detail/AdminOperatorDetailPage.tsx
```

Сохранить текущие блоки входов, затем добавить:

```text
Количество тренировок
Средний балл
Среднее время реакции
Количество критических ошибок
Динамика результата
Профиль навыков
Последние тренировки
AI-рекомендация следующего сценария
```

## 35. Новые компоненты

```text
frontend/src/widgets/operator-skill-profile/OperatorSkillProfile.tsx
frontend/src/widgets/operator-training-history/OperatorTrainingHistory.tsx
frontend/src/widgets/operator-recommendation/OperatorRecommendationCard.tsx
```

---

# Этап 12. LLM/RAG

## 36. Назначение LLM

LLM используется только для:

- понятного объяснения выявленной ошибки;
- формирования короткого персонального debrief;
- ответа «почему это было ошибкой»;
- пересказа релевантного технологического требования.

LLM не используется для:

- расчёта параметров установки;
- определения authoritative state;
- отправки команд;
- самостоятельного выставления итогового балла;
- принятия решений о безопасности.

## 37. RAG

Если в систему загружаются технологические регламенты:

```text
source document
→ chunks
→ embeddings
→ vector store
→ retrieval по error/process context
→ LLM explanation
```

Ответ должен сохранять `source_id`, раздел/страницу и текстовый фрагмент, чтобы в UI можно было показать источник.

---

# Этап 13. Отказоустойчивость и безопасность

## 38. Fail-open для тренажёра

Если AI-service недоступен:

```text
тренажёр продолжает работать
физическая модель продолжает работать
команды оператора продолжают исполняться
assessment rules продолжают работать
AI-подсказки временно недоступны
```

AI не должен быть single point of failure.

## 39. Таймауты

Для realtime prediction выставить малый timeout, например 300–800 мс в зависимости от инфраструктуры. Не ждать LLM в основном command path.

`sendSimulationCommand()` не должен синхронно зависеть от AI.

## 40. Логи и аудит

Сохранять:

```text
model_version
prediction timestamp
input feature version
risk score
predicted class
LLM model/version
source references
AI errors/timeouts
```

Это позволяет воспроизводить решения системы.

---

# Этап 14. Тесты

## 41. Backend tests

Добавить:

```text
backend/tests/services/test_assessment.py
backend/tests/services/test_simulation_events.py
backend/tests/services/test_skill_profile.py
backend/tests/integrations/ai/test_http_gateway.py
backend/tests/api/test_training.py
```

Проверки:

- timeline создаётся в правильном порядке;
- повторный snapshot той же revision не дублируется;
- команда сохраняется до внешнего ответа;
- ошибка правила определяется детерминированно;
- AI timeout не ломает сессию;
- operator не видит чужую тренировку;
- exam mode не отдаёт realtime hints.

## 42. Frontend tests

Добавить тесты для:

```text
AiCoachPanel
OperatorSessionResultPage
OperatorSkillProfile
```

Проверить:

- risk отображается корректно;
- AI unavailable не ломает UI;
- exam mode скрывает hint;
- timeline визуально различает prediction и actual error.

## 43. E2E

Playwright сценарий:

```text
login operator
→ choose simulator
→ choose training scenario
→ start session
→ perform wrong/late action
→ observe AI warning
→ finish session
→ open debrief
→ verify error and recommendation
```

---

# Этап 15. Docker и конфигурация

## 44. `docker-compose.yml`

Добавить сервис:

```text
ai-service
```

Переменные текущего backend:

```text
AI_SERVICE_URL
AI_SERVICE_CONNECT_TIMEOUT
AI_SERVICE_READ_TIMEOUT
AI_ENABLED
```

Переменные AI-service:

```text
MODEL_PATH
MODEL_VERSION
LLM_PROVIDER
LLM_BASE_URL
LLM_MODEL
RAG_ENABLED
```

Не хранить секреты в Git.

---

# Этап 16. Порядок реализации

## P0 — фундамент, обязателен

1. `SimulationEvent` + миграция.
2. Сохранение команд и snapshots в timeline.
3. Server-side telemetry collector.
4. `TrainingScenario` и привязка сценария к сессии.
5. `AssessmentService` + 4–6 правил.
6. `OperatorError` + `TrainingResult`.
7. API результатов.
8. Страница итогового разбора.

После P0 система уже реально оценивает действия оператора и соответствует базовой задаче КТК.

## P1 — главное AI-усиление

9. Отдельный `ai-service`.
10. Risk prediction endpoint.
11. Dataset generation на цифровом двойнике.
12. CatBoost risk model.
13. `AiCoachPanel`.
14. Сохранение prediction в timeline.
15. Демонстрация «prediction до actual error».

## P2 — персонализация

16. `OperatorSkillProfile`.
17. Skill profile UI администратора.
18. Recommendation service.
19. Автоподбор следующего сценария.

## P3 — LLM/RAG

20. Explanation endpoint.
21. LLM debrief.
22. RAG по технологическим материалам.
23. Источники и ссылки в объяснении.

---

# 17. Критерий готовности MVP

MVP AI-интеграции можно считать готовым, если демонстрационный сценарий позволяет показать полный цикл:

```text
1. Оператор запускает тренировку.
2. Backend независимо собирает telemetry и действия.
3. Параметры процесса начинают отклоняться.
4. AI заранее повышает риск конкретной ошибки.
5. Оператор совершает или не успевает предотвратить ошибку.
6. Rules Engine фиксирует её тип, место и причинный контекст.
7. Сессия завершается с объективной оценкой.
8. Оператор получает понятный debrief.
9. Администратор видит обновлённый профиль навыков.
10. Система рекомендует следующую тренировку.
```

Именно эта вертикальная цепочка важнее количества отдельных AI-функций.
