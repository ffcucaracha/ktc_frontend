# ktc_frontend

Веб-приложение для обучения операторов работе с технологической установкой. MVP содержит демонстрационную установку: котёл, насос подачи пара и насос откачки пара.

Проект отвечает за аутентификацию, управление операторами, историю входов, каталог тренажёров, локальные сессии, визуализацию установки и интеграцию с отдельным сервисом моделирования.

> Физическая логика, математическая модель, расчёт параметров, межблокировки и аварийные условия реализуются другим разработчиком в отдельном сервисе. В этом репозитории они не дублируются.

## 1. Функции MVP

### Администратор

- вход в систему;
- просмотр, создание, активация и деактивация операторов;
- сброс пароля оператора;
- карточка оператора;
- количество успешных входов;
- дата последнего успешного входа;
- история входов оператора.

### Оператор

- вход в систему;
- просмотр доступных тренажёров;
- выбор тренажёра «Котёл с двумя насосами»;
- запуск и завершение сессии;
- просмотр состояния котла и насосов;
- запуск и остановка насосов подачи и откачки пара;
- просмотр pending/accepted/rejected состояния команды;
- получение обновлений, аварий и ошибок внешнего сервиса.

## 2. Не входит в MVP

- физическая и математическая модель;
- расчёт давления, температуры и расхода;
- AI-наставник и оценивание;
- редактор установки и сценариев;
- 3D-визуализация;
- самостоятельная регистрация;
- восстановление пароля по email.

## 3. Архитектура

```mermaid
flowchart LR
    F[React frontend] -->|REST и WebSocket| B[FastAPI application backend]
    B -->|REST-команды| S[External simulation service]
    S -->|WebSocket events или polling| B
    B --> P[(PostgreSQL)]
```

Frontend обращается только к application backend. Backend является BFF и anti-corruption layer:

- проверяет аутентификацию, роль и владельца сессии;
- хранит пользователей, историю входов и локальные сессии;
- передаёт команды внешнему сервису;
- нормализует внешние DTO и ошибки;
- сохраняет журнал команд и последний snapshot;
- транслирует нормализованные события frontend;
- скрывает адреса и credentials внешнего сервиса.

## 4. Стек

### Frontend

- React + TypeScript strict;
- Vite;
- React Router;
- TanStack Query для server state;
- Zustand для небольшого client state;
- Material UI;
- React Hook Form + Zod;
- SVG для мнемосхемы;
- Vitest + React Testing Library + MSW;
- Playwright.

### Backend

- Python 3.12+;
- FastAPI + Pydantic v2;
- SQLAlchemy 2 async + asyncpg;
- Alembic + PostgreSQL;
- PyJWT;
- pwdlib с Argon2;
- httpx + WebSocket;
- pytest, Ruff, mypy.

### Инфраструктура

- Docker и Docker Compose;
- Nginx опционально для production;
- `.env`;
- структурированные JSON-логи.

Источником истины по версиям являются lock-файлы, а не README.

## 5. Структура репозитория

```text
.
├── AGENTS.md
├── README.md
├── CODEX_PROMPTS.md
├── .env.example
├── docker-compose.yml
├── contracts/
│   └── simulation-api/
│       ├── openapi.yaml
│       ├── websocket-events.md
│       └── examples/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/endpoints/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── websocket/
│   │   ├── commands/
│   │   └── integrations/simulation/
│   │       ├── base.py
│   │       ├── dto.py
│   │       ├── http_gateway.py
│   │       ├── mock_gateway.py
│   │       └── factory.py
│   └── tests/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── app/
    │   ├── pages/
    │   ├── widgets/
    │   ├── features/
    │   ├── entities/
    │   └── shared/
    └── tests/
```

## 6. Роли и права

| Операция | Admin | Operator |
|---|---:|---:|
| Вход и свой профиль | Да | Да |
| CRUD операторов | Да | Нет |
| История входов | Да | Нет |
| Каталог тренажёров | Опционально | Да |
| Запуск и управление сессией | Нет | Да |
| Собственная активная сессия | Нет | Да |

Проверка прав обязательна на backend. Скрытая кнопка на frontend не является авторизацией.

## 7. Аутентификация

- логин по `username` и паролю;
- короткоживущий access JWT;
- access token хранится только в памяти frontend;
- refresh token передаётся в `HttpOnly`, `Secure`, `SameSite=Lax` cookie;
- refresh token ротируется;
- в БД хранится hash refresh token;
- logout отзывает текущий refresh token;
- деактивированный пользователь не может login/refresh;
- ошибка входа не раскрывает существование пользователя.

Первый администратор создаётся CLI-командой, без пароля в Git:

```bash
uv run python -m app.commands.create_admin
```

## 8. Модели данных

### User

```text
id UUID
username string unique
full_name string
role admin | operator
password_hash string
is_active boolean
created_at timestamptz
updated_at timestamptz
```

### RefreshToken

```text
id UUID
user_id UUID
 token_hash string
expires_at timestamptz
revoked_at timestamptz nullable
replaced_by_id UUID nullable
created_at timestamptz
```

### LoginEvent

```text
id UUID
user_id UUID nullable
username_entered string
success boolean
failure_reason enum nullable
occurred_at timestamptz
ip_address inet nullable
user_agent text nullable
```

### SimulatorDefinition

```text
id UUID
code string unique
external_id string
name string
description text
visualization_type string
is_active boolean
```

Seed MVP:

```text
code: boiler-demo
external_id: boiler-001
name: Котёл с двумя насосами
visualization_type: boiler-v1
```

### SimulationSession

```text
id UUID
operator_id UUID
simulator_definition_id UUID
external_session_id string nullable
status creating | active | stopping | completed | failed
started_at timestamptz nullable
ended_at timestamptz nullable
last_state JSONB nullable
error_code string nullable
error_message text nullable
created_at timestamptz
updated_at timestamptz
```

### SimulationCommand

```text
id UUID
session_id UUID
command_id UUID unique
equipment_id string
action string
payload JSONB
status pending | accepted | rejected | failed
external_error_code string nullable
external_error_message text nullable
created_at timestamptz
completed_at timestamptz nullable
```

## 9. Локальное API

Префикс REST: `/api/v1`.

### Auth

| Method | Path |
|---|---|
| POST | `/auth/login` |
| POST | `/auth/refresh` |
| POST | `/auth/logout` |
| GET | `/auth/me` |

### Operators

| Method | Path |
|---|---|
| GET | `/operators` |
| POST | `/operators` |
| GET | `/operators/{operator_id}` |
| PATCH | `/operators/{operator_id}` |
| POST | `/operators/{operator_id}/reset-password` |
| GET | `/operators/{operator_id}/login-history` |
| GET | `/operators/{operator_id}/login-stats` |

### Simulators and sessions

| Method | Path |
|---|---|
| GET | `/simulators` |
| GET | `/simulators/{simulator_id}` |
| POST | `/simulation-sessions` |
| GET | `/simulation-sessions/{session_id}` |
| GET | `/simulation-sessions/{session_id}/state` |
| POST | `/simulation-sessions/{session_id}/commands` |
| POST | `/simulation-sessions/{session_id}/stop` |

WebSocket:

```text
/ws/v1/simulation-sessions/{session_id}
```

WebSocket разрешён только владельцу сессии.

## 10. Контракт с simulation service

Контракт фиксируется в `contracts/simulation-api/openapi.yaml` и `websocket-events.md`. Фактические URL согласовываются с разработчиком модуля моделирования.

Минимальные операции внешнего сервиса:

```text
POST /v1/sessions
GET  /v1/sessions/{external_session_id}/state
POST /v1/sessions/{external_session_id}/commands
POST /v1/sessions/{external_session_id}/stop
WS   /v1/sessions/{external_session_id}/events
```

### Создание сессии

```json
{
  "simulator_id": "boiler-001",
  "operator_id": "06b14858-8023-4916-88dc-4b44d705086c",
  "metadata": {
    "local_session_id": "e26e496f-4200-4c9c-b105-aaea54ac8958"
  }
}
```

Пример ответа:

```json
{
  "session_id": "external-session-123",
  "status": "active",
  "state": {
    "revision": 1,
    "simulation_time_ms": 0,
    "boiler": {
      "temperature_c": 100.0,
      "pressure_bar": 1.0,
      "status": "idle"
    },
    "equipment": {
      "steam_supply_pump": {"status": "stopped", "flow_kg_h": 0},
      "steam_exhaust_pump": {"status": "stopped", "flow_kg_h": 0}
    },
    "alarms": []
  }
}
```

### Команда

```json
{
  "command_id": "735f13c8-6700-4ad6-b86b-f5d2e8b683d3",
  "equipment_id": "steam_supply_pump",
  "action": "start",
  "payload": {},
  "expected_revision": 1
}
```

Допустимые команды MVP:

```text
steam_supply_pump: start, stop
steam_exhaust_pump: start, stop
```

HTTP `accepted` означает только принятие команды. Состояние UI изменяется после нового авторитетного snapshot/event.

## 11. Нормализованный state

```json
{
  "revision": 12,
  "simulation_time_ms": 45000,
  "boiler": {
    "temperature_c": 122.4,
    "pressure_bar": 1.8,
    "status": "running"
  },
  "equipment": {
    "steam_supply_pump": {"status": "running", "flow_kg_h": 120},
    "steam_exhaust_pump": {"status": "stopped", "flow_kg_h": 0}
  },
  "alarms": [
    {
      "code": "PRESSURE_HIGH",
      "severity": "warning",
      "message": "Повышенное давление",
      "active": true
    }
  ]
}
```

Статусы насоса:

```text
stopped, starting, running, stopping, fault, unavailable
```

Внешние значения преобразуются адаптером во внутренние enum.

## 12. WebSocket-события frontend

Типы MVP:

```text
session.ready
state.snapshot
state.patch
command.accepted
command.rejected
alarm.raised
alarm.cleared
integration.error
session.completed
session.failed
```

Пример:

```json
{
  "type": "command.rejected",
  "data": {
    "command_id": "735f13c8-6700-4ad6-b86b-f5d2e8b683d3",
    "code": "INTERLOCK_ACTIVE",
    "message": "Команда заблокирована внешним сервисом"
  }
}
```

## 13. Реакция на действие оператора

```mermaid
sequenceDiagram
    participant U as Operator
    participant F as React
    participant B as FastAPI
    participant S as Simulation service

    U->>F: Нажимает «Запустить»
    F->>F: pending и блокировка дубля
    F->>B: POST command
    B->>B: RBAC, ownership, command journal
    B->>S: Передаёт command_id и команду
    S-->>B: accepted или rejected
    B-->>F: HTTP-результат
    S-->>B: state.snapshot/state.patch
    B->>B: Обновляет last_state
    B-->>F: WebSocket state
    F->>F: Обновляет SVG
```

Правила frontend:

- не применять состояние оптимистично;
- после клика показывать pending;
- блокировать повтор той же команды;
- при rejected показывать причину;
- при timeout не менять оборудование;
- после reconnect запрашивать snapshot;
- игнорировать state с меньшим `revision`;
- не вычислять технологические параметры.

## 14. Визуализация

SVG-экран содержит:

- котёл;
- насос подачи пара и входную линию;
- насос откачки пара и выходную линию;
- температуру и давление;
- статус сессии и соединения;
- активные аварии;
- кнопки start/stop;
- журнал последних команд.

Пример структуры:

```text
widgets/boiler-simulator/
├── BoilerSimulator.tsx
├── BoilerScheme.tsx
├── Pump.tsx
├── Gauge.tsx
├── AlarmPanel.tsx
├── CommandLog.tsx
└── __tests__/
```

Состояние передаётся не только цветом: нужны текст, иконка и `aria-label`.

## 15. SimulationGateway

```python
class SimulationGateway(Protocol):
    async def create_session(...) -> ExternalSession: ...
    async def get_state(...) -> SimulationState: ...
    async def send_command(...) -> CommandResult: ...
    async def stop_session(...) -> None: ...
    async def stream_events(...) -> AsyncIterator[SimulationEvent]: ...
```

Реализации:

- `HttpSimulationGateway` — реальный сервис;
- `MockSimulationGateway` — локальная разработка и тесты.

Mock может переключать только статус выбранного насоса и выдавать подготовленные события. Он не рассчитывает давление, температуру и расход.

## 16. Ошибки интеграции

Внутренние коды:

```text
SIMULATION_SERVICE_UNAVAILABLE
SIMULATION_TIMEOUT
SIMULATION_PROTOCOL_ERROR
SIMULATION_SESSION_NOT_FOUND
COMMAND_REJECTED
STALE_STATE_REVISION
INVALID_EXTERNAL_PAYLOAD
```

Требования к HTTP-клиенту:

- connect/read timeout;
- connection pool;
- correlation ID;
- логирование duration/status без secrets;
- retry только безопасных идемпотентных операций;
- уникальный `command_id` как idempotency key;
- нормализация внешних ошибок.

## 17. Конфигурация

```dotenv
APP_ENV=local
APP_NAME=ktc_frontend
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://trainer:trainer@postgres:5432/trainer
JWT_SECRET=change-me-in-local-development-only-32-bytes
JWT_ALGORITHM=HS256
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=14
COOKIE_SECURE=false
CORS_ORIGINS=http://localhost:5173
SIMULATION_GATEWAY_MODE=mock
SIMULATION_API_BASE_URL=http://simulation-service:8080
SIMULATION_WS_BASE_URL=ws://simulation-service:8080
SIMULATION_API_KEY=change-me
KTC_API_BASE_URL=http://ktc-backend:8000
SIMULATION_CONNECT_TIMEOUT_SECONDS=3
SIMULATION_READ_TIMEOUT_SECONDS=10
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_BASE_URL=ws://localhost:8000/ws/v1
```

## 18. Запуск

```bash
cp .env.example .env
docker compose up --build
```

Compose поднимает PostgreSQL, backend, frontend и `ktc_backend`. Backend при старте применяет
Alembic migrations, идемпотентно создаёт тренажёры, тестовых пользователей и работает с
`SIMULATION_GATEWAY_MODE=mock` для первого тренажёра.

Адреса локального стенда:

```text
Frontend: http://localhost:5173
Backend health: http://localhost:8000/health/ready
KTC backend: http://localhost:8001
PostgreSQL: localhost:55439
```

Тестовые пользователи создаются командой `app.commands.seed_e2e_admin` из переменных
`E2E_ADMIN_*` и `E2E_OPERATOR_*`.

Backend без Docker:

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

E2E стенд:

```bash
cp .env.example .env
docker compose up --build -d
cd frontend
npm install
npm run e2e
```

Playwright setup ждёт `/health/ready` и frontend, затем создаёт admin через backend CLI.
Пароли берутся из `E2E_ADMIN_PASSWORD` и `E2E_OPERATOR_PASSWORD`; они не логируются приложением.

## 19. Проверки

Backend:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Frontend:

```bash
npm run lint
npm run typecheck
npm run test
npm run build
npm run e2e
```

Полный локальный прогон через Docker:

```bash
docker compose up --build -d
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
RUN_POSTGRES_TESTS=1 TEST_DATABASE_URL=postgresql+asyncpg://trainer:trainer@localhost:55439/trainer uv run pytest
cd ../frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run e2e
```

## 20. Критические тесты

- login success/failure/inactive;
- refresh rotation и logout;
- RBAC;
- admin создаёт и деактивирует оператора;
- login history и stats;
- operator получает каталог и создаёт сессию;
- ownership сессии;
- command accepted/rejected/timeout;
- WebSocket auth и reconnect;
- stale revision;
- E2E: admin создаёт operator, operator входит, запускает насос и получает authoritative state.

## 21. Definition of Done MVP

- запуск одной командой Docker Compose;
- миграции применяются на чистой БД;
- admin создаётся CLI-командой;
- admin управляет операторами и видит историю входов;
- operator открывает boiler-demo;
- mock и HTTP gateway реализуют один интерфейс;
- frontend не знает внешний формат simulation service;
- команды обоих насосов проходят полный путь;
- состояние приходит через WebSocket;
- ошибки нормализуются;
- backend/frontend/E2E тесты проходят;
- в коде нет физической модели;
- secrets и временные пароли не попадают в Git и логи.
