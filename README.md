# KTC — компьютерный тренажёр оператора с AI-поддержкой

Монорепозиторий application-части компьютерного тренажёрного комплекса для обучения операторов технологической установки. Основной демонстрационный контур — блок подогрева сырой нефти перед ЭЛОУ; физическая модель и технологическая динамика находятся в отдельном сервисе `ktc_backend` и подключаются через API.

Проект реализует аутентификацию, управление операторами, учебные сценарии, сбор timeline, детерминированную оценку действий, ML-прогноз риска ошибки, LLM-объяснения, профиль навыков и персональные рекомендации следующей тренировки.

> Ключевая граница архитектуры: этот репозиторий **не рассчитывает физику процесса, межблокировки и аварийную логику**. Authoritative process state всегда приходит из сервиса моделирования. AI также не имеет права управлять установкой или выставлять фактическую ошибку вместо rules engine.

## Что умеет MVP

### Оператор

- вход в систему;
- выбор тренажёра и учебного сценария;
- режимы `training` и `exam`;
- управление оборудованием через backend;
- получение authoritative snapshot от цифрового двойника;
- realtime AI Coach в режиме обучения;
- скрытие AI-подсказок во время экзамена при сохранении аналитики на backend;
- итоговая оценка после сессии;
- timeline действий, ML-прогнозов и фактических ошибок;
- человекочитаемый debrief;
- переход к рекомендованному следующему сценарию.

### Администратор

- создание, активация и деактивация операторов;
- сброс пароля;
- история и статистика входов;
- история тренировок;
- средний балл, реакция и критические ошибки;
- профиль навыков;
- персональная рекомендация следующей тренировки.

### AI-контур

- CatBoost risk prediction на горизонте 10 секунд;
- feature engineering из telemetry/action history без использования будущих данных;
- аудит `model_version`, feature version, risk и ошибок AI;
- OpenAI-compatible LLM для объяснения уже классифицированных ошибок и debrief;
- deterministic fallback при недоступности AI;
- RAG предусмотрен архитектурой, но сознательно вынесен за рамки MVP.

## Архитектура

```mermaid
flowchart LR
    U[Operator/Admin] --> F[React + TypeScript]
    F -->|REST / WebSocket| B[FastAPI application backend]
    B -->|REST| K[ktc_backend / digital twin]
    K -->|authoritative telemetry| B
    B --> P[(PostgreSQL)]
    B -->|AI gateway| A[ai-service]
    A --> M[CatBoost model]
    A --> L[OpenAI-compatible LLM]
```

Разделение ответственности:

```text
ktc_backend
  = истина о технологическом процессе

application backend
  = истина о пользователях, сессиях, сценариях, timeline, assessment и профиле обучения

ai-service
  = прогноз риска и текстовое объяснение уже проверенных фактов
```

Полный учебный цикл:

```text
telemetry + operator actions
        ↓
SimulationEvent timeline
        ↓
Rules-based AssessmentService
        ↓
OperatorError + TrainingResult
        ↓
OperatorSkillProfile
        ↓
персональная рекомендация сценария

параллельно:
telemetry window → CatBoost risk prediction → ai.risk.updated

после сессии:
verified assessment facts → LLM/fallback → debrief
```

## Стек

### Frontend

- React 18 + TypeScript;
- Vite;
- React Router;
- TanStack Query;
- Zustand;
- Material UI;
- React Hook Form + Zod;
- Vitest + React Testing Library + MSW;
- Playwright.

### Application backend

- Python 3.12+;
- FastAPI + Pydantic v2;
- SQLAlchemy 2 async + asyncpg;
- Alembic + PostgreSQL;
- PyJWT;
- Argon2 через `pwdlib`;
- httpx + WebSocket;
- pytest + Ruff + mypy.

### AI service

- Python 3.12+;
- FastAPI;
- CatBoost;
- OpenAI-compatible LLM client;
- pytest.

### Infrastructure

- Docker Compose;
- PostgreSQL 16;
- отдельные контейнеры frontend, backend, ai-service;
- внешний/соседний `ktc_backend` для моделирования.

## Структура репозитория

```text
.
├── README.md
├── AGENTS.md
├── AI_INTEGRATION_DECOMPOSITION.md
├── AI_DEPLOYMENT.md
├── AI_TESTING.md
├── MVP_READINESS.md
├── ДЛЯ_ЛЕНЫ.md
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── integrations/
│   │   │   ├── simulation/
│   │   │   └── ai/
│   │   ├── models/
│   │   ├── repositories/
│   │   └── services/
│   └── tests/
├── frontend/
│   ├── src/
│   ├── tests/
│   └── e2e/
└── ai-service/
    ├── README.md
    ├── ML_RISK_MODEL_RUNBOOK.md
    ├── app/
    ├── scripts/
    ├── datasets/
    ├── models/
    └── tests/
```

## Учебные сценарии MVP

Для блока подогрева нефти seed создаёт:

- `oil-heating-basic-startup` — базовый запуск H1A → H1B → H1V;
- `oil-heating-basic-shutdown` — учебная остановка;
- `oil-heating-flow-control` — работа с FRC404/FRC405/FRC406;
- `oil-heating-wrong-sequence-training` — отработка порядка операций;
- `oil-heating-reaction-time-training` — сокращённые допустимые интервалы реакции.

Также сохранён демонстрационный `boiler-demo` с двумя насосами для mock-разработки.

Сценарий хранит expected actions, допустимую задержку, ограничения payload и assessment metadata. Физические последствия действий сценарий не рассчитывает.

## Assessment и ошибки

Фактические ошибки определяет `AssessmentService` по сохранённому timeline. Для MVP используются категории:

```text
WRONG_ACTION
LATE_ACTION
MISSED_ACTION
WRONG_SEQUENCE
```

Для каждой сессии формируются:

- `TrainingResult`;
- `OperatorError[]`;
- оценки sequence/reaction/safety;
- reaction time;
- итоговый score;
- профиль компетенций оператора.

LLM не определяет тип ошибки и не изменяет итоговый score.

## Персонализация

После завершения сессии событие `session.completed` обрабатывается отдельным post-session processor:

```text
session.completed
  → final assessment
  → rebuild OperatorSkillProfile
  → recommendations
```

Обработка идемпотентна и допускает повторные попытки. Ошибка аналитики не отменяет завершение тренировки.

Для следующей тренировки backend выбирает **конкретный активный сценарий** на основании assessment metadata и приоритетного навыка. LLM может объяснить рекомендацию, но не выбирает scenario code.

## ML risk prediction

`ai-service` прогнозирует бинарный target:

```text
ERROR_IN_NEXT_10_SECONDS = 0 / 1
```

Используются признаки давления, температуры, насосов, регуляторов, alarms, последних действий и предыдущих ошибок. Feature extraction использует только информацию, доступную к моменту прогноза.

Без обученной модели сервис остаётся healthy и возвращает явный fallback `risk-model-unavailable-v1`.

Полный процесс подготовки данных и обучения описан в:

- `ai-service/ML_RISK_MODEL_RUNBOOK.md`;
- `ai-service/README.md`.

Экспорт накопленных сессий:

```bash
cd backend
python -m app.commands.export_ml_sessions --output /tmp/session_exports.jsonl
```

Далее:

```bash
cd ../ai-service
python -m scripts.generate_dataset /tmp/session_exports.jsonl datasets/risk.csv
python -m scripts.train_risk_model datasets/risk.csv
```

Большие datasets и бинарные модели намеренно не коммитятся.

## LLM и RAG

LLM используется только для:

- объяснения уже выявленной ошибки;
- учебной рекомендации;
- итогового debrief.

По умолчанию LLM выключена. Поддерживается OpenAI-compatible endpoint.

RAG в MVP не реализован. Следующее расширение:

```text
технологические документы
→ chunks
→ embeddings
→ vector store
→ retrieval по контексту ошибки
→ LLM explanation
→ source_id / раздел / страница
```

Это позволит обосновывать объяснение конкретным пунктом регламента без переноса технологической логики в LLM.

## Fail-open

AI не является single point of failure.

Если `ai-service` или LLM недоступны:

```text
цифровой двойник продолжает работать
команды оператора продолжают работать
telemetry продолжает собираться
rules assessment продолжает работать
AI hints временно отсутствуют
LLM debrief заменяется deterministic fallback
```

Realtime prediction имеет отдельный короткий timeout.

## Основные API

REST prefix: `/api/v1`.

### Auth / operators

```text
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/me

GET  /operators
POST /operators
GET  /operators/{operator_id}
PATCH /operators/{operator_id}
GET  /operators/{operator_id}/login-history
GET  /operators/{operator_id}/login-stats
GET  /operators/{operator_id}/training-results
GET  /operators/{operator_id}/skill-profile
GET  /operators/{operator_id}/recommendations
```

### Simulation / training

```text
GET  /simulators
GET  /simulators/{simulator_id}
GET  /simulators/{simulator_id}/scenarios
POST /simulation-sessions
GET  /simulation-sessions/{session_id}
GET  /simulation-sessions/{session_id}/state
POST /simulation-sessions/{session_id}/commands
POST /simulation-sessions/{session_id}/stop
GET  /simulation-sessions/{session_id}/assessment
GET  /simulation-sessions/{session_id}/errors
GET  /simulation-sessions/{session_id}/timeline
GET  /simulation-sessions/{session_id}/debrief
```

WebSocket:

```text
/ws/v1/simulation-sessions/{session_id}
/ws/v1/simulation-sessions/{session_id}/training
```

Доступ к операторской сессии проверяется на backend по владельцу.

## Локальный запуск

Требуется соседний каталог `../ktc_backend`, так как compose собирает сервис моделирования из него.

```bash
cp .env.example .env
docker compose up --build
```

Локальные адреса:

```text
Frontend:       http://localhost:5173
Backend ready:  http://localhost:8000/health/ready
KTC backend:    http://localhost:8001
AI service:     http://localhost:8090
PostgreSQL:     localhost:55439
```

По умолчанию:

```env
AI_ENABLED=true
AI_GATEWAY_MODE=mock
AI_LLM_MODE=disabled
RAG_ENABLED=false
```

Для реального ML через `ai-service`:

```env
AI_ENABLED=true
AI_GATEWAY_MODE=http
AI_SERVICE_BASE_URL=http://ai-service:8090
```

Подробнее: `AI_DEPLOYMENT.md`.

## Запуск без Docker

Backend:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.commands.seed_simulators
uv run python -m app.commands.create_admin
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

AI service:

```bash
cd ai-service
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8090
```

## Проверки

Backend unit/contract:

```bash
cd backend
pytest
ruff check app tests
mypy app
```

Backend PostgreSQL integration:

```bash
RUN_POSTGRES_TESTS=1 \
TEST_DATABASE_URL=postgresql+asyncpg://trainer:trainer@localhost:55439/trainer \
pytest
```

AI service:

```bash
cd ai-service
pytest
```

Frontend:

```bash
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
npm run e2e
```

Описание критических проверок: `AI_TESTING.md`.

## Документация

- `AI_INTEGRATION_DECOMPOSITION.md` — исходная декомпозиция AI-интеграции;
- `ai-service/ML_RISK_MODEL_RUNBOOK.md` — сбор данных, dataset и обучение CatBoost;
- `AI_DEPLOYMENT.md` — режимы запуска и environment;
- `AI_TESTING.md` — test matrix;
- `MVP_READINESS.md` — итоговый чек-лист и внешние prerequisites;
- `ДЛЯ_ЛЕНЫ.md` — материалы для презентации, включая план RAG после MVP.

## Что ещё требуется для полноценной демонстрации ML

Кодовый контур MVP собран, но **обученный CatBoost artifact намеренно не находится в Git**. Для реального ненулевого прогноза необходимо накопить/экспортировать репрезентативные сессии цифрового двойника, обучить модель по runbook и поместить `.cbm` + metadata в `ai-service/models/`.

Также перед защитой необходимо фактически прогнать backend/frontend/AI/E2E тесты на целевой машине и проверить реальные имена/единицы telemetry, поступающие из актуальной версии `ktc_backend`.
