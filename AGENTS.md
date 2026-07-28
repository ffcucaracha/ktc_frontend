# AGENTS.md

Инструкции для Codex и других coding agents, работающих с репозиторием тренажёра.

## 1. Перед началом

Перед любым изменением:

1. Прочитай `README.md` и этот файл целиком.
2. Изучи дерево проекта и существующие соглашения.
3. Проверь незакоммиченные изменения и не перезаписывай работу пользователя.
4. Определи затрагиваемые модули, миграции, API-контракты и тесты.
5. Сформулируй краткий план.
6. Не меняй архитектурные границы без явного указания пользователя.

При противоречии документов и кода выбери наиболее безопасное минимальное изменение и укажи противоречие в итоговом отчёте. Не додумывай технологическую логику установки.

## 2. Критическая граница проекта

Этот репозиторий не реализует:

- физическую модель установки;
- расчёт температуры, давления, расхода и других параметров;
- технологические зависимости и межблокировки;
- правила аварий;
- AI-логику;
- оценку правильности действий оператора.

Эти функции принадлежат внешнему `simulation service`.

Запрещено:

- добавлять формулы процесса во frontend или application backend;
- моделировать процесс в production-коде;
- вычислять новое состояние котла после команды пользователя;
- считать команду применённой до авторитетного state/event;
- обращаться из frontend прямо к simulation service;
- передавать frontend URL, credentials или payload внешнего сервиса;
- исполнять или прокидывать внешний payload без валидации и mapping.

Разрешённый mock может:

- вернуть fixture начального состояния;
- дать заранее заданный accepted/rejected ответ;
- переключить только статус выбранного насоса;
- выдать подготовленный alarm/error event;
- имитировать timeout/disconnect.

Mock не рассчитывает физические параметры.

## 3. Архитектура

```text
React frontend
      |
      | REST + WebSocket
      v
FastAPI application backend
      |
      | SimulationGateway
      v
External simulation service
```

Backend является:

- BFF для frontend;
- точкой auth/RBAC;
- владельцем пользователей, login history и локальных сессий;
- владельцем command journal;
- anti-corruption layer внешнего API;
- WebSocket relay нормализованных событий.

Любой внешний вызов проходит через `SimulationGateway`. Endpoint, service и React-компонент не зависят от конкретного внешнего HTTP payload.

## 4. Стек

### Backend

- Python 3.12+;
- FastAPI, Pydantic v2;
- SQLAlchemy 2 async, PostgreSQL, asyncpg, Alembic;
- httpx, WebSocket;
- PyJWT, pwdlib/Argon2;
- pytest, Ruff, mypy.

### Frontend

- React, TypeScript strict, Vite;
- React Router;
- TanStack Query;
- Zustand только для client state;
- Material UI;
- React Hook Form, Zod;
- SVG;
- Vitest, React Testing Library, MSW, Playwright.

Не добавляй framework или библиотеку с дублирующей ответственностью без необходимости.

## 5. Общие правила

- Делай минимальное изменение, полностью решающее задачу.
- Не создавай абстракции без второго реального use case.
- Не смешивай transport, application, domain и infrastructure.
- Не помещай прикладную логику в endpoint или React page.
- Не используй глобальные mutable singleton для пользовательского состояния.
- Не оставляй `TODO`, `pass` и заглушки вместо требуемой реализации.
- Не маскируй ошибки пустыми `except`/`catch`.
- Не логируй passwords, JWT, refresh tokens, API keys и cookies.
- Не меняй публичный контракт без тестов и документации.
- Даты — timezone-aware UTC.
- Идентификаторы доменных сущностей — UUID.
- Enum имеют явные строковые значения.
- Пользовательские сообщения — по-русски.
- Имена кода и API-полей — по-английски.

## 6. Backend: зависимости слоёв

```text
api endpoints
    -> application services
        -> repositories / SimulationGateway
            -> SQLAlchemy / httpx
```

### Endpoint

Endpoint только:

- читает HTTP-вход;
- вызывает auth/RBAC dependency;
- вызывает application service;
- возвращает response schema.

Endpoint не выполняет SQL, не хэширует пароль, не вызывает httpx и не нормализует внешние ошибки.

### Service

Service реализует use case:

- прикладные проверки;
- orchestration repository/gateway;
- транзакционную границу;
- прикладные ошибки.

### Repository

Repository отвечает за доступ к данным конкретной сущности. Не создавай generic repository, ухудшающий читаемость.

### DTO

Разделяй:

- API request/response schemas;
- internal application DTO;
- external simulation DTO;
- SQLAlchemy models.

Не возвращай SQLAlchemy model напрямую из endpoint.

## 7. База данных

- Любое изменение схемы — Alembic migration.
- `upgrade` и `downgrade` обязательны.
- Не редактируй применённую миграцию, если можно создать новую.
- Constraints должны быть в БД, не только в Pydantic.
- Foreign key deletion задаётся явно.
- Добавляй индексы под реальные запросы.
- Используй стабильную сортировку и пагинацию.
- Не удаляй пользователей физически: `is_active`.
- Не допускай скрытый lazy loading после закрытия async session.
- `last_state` и command payload допустимы в JSONB; фильтруемые поля нормализуются.

## 8. Auth и RBAC

- Роли: `admin`, `operator`.
- Авторизация всегда проверяется на backend.
- Ошибка login должна быть generic.
- Password хранится как Argon2 hash.
- Access token короткоживущий, не хранится в БД.
- Refresh token ротируется и отзывается.
- В БД хранится hash refresh token.
- Logout отзывает token.
- Неактивный пользователь не может login/refresh.
- Начальный admin создаётся CLI-командой.
- Temporary password возвращается один раз и не логируется.
- LoginEvent создаётся для success и failure.
- Оператор не получает login history других пользователей.
- Не доверяй роли из request body.
- Используй общие `current_user`, `require_admin`, `require_operator` dependencies.

## 9. Simulation integration

Интерфейс:

```python
class SimulationGateway(Protocol):
    async def create_session(...) -> ExternalSession: ...
    async def get_state(...) -> SimulationState: ...
    async def send_command(...) -> CommandResult: ...
    async def stop_session(...) -> None: ...
    async def stream_events(...) -> AsyncIterator[SimulationEvent]: ...
```

Реализации:

- `HttpSimulationGateway`;
- `MockSimulationGateway`.

Factory выбирает gateway через `SIMULATION_GATEWAY_MODE`.

Правила:

- внешний payload валидируется Pydantic-моделями;
- внешний enum преобразуется во внутренний;
- внешние exception не выходят за integration layer;
- ошибки преобразуются в типизированные integration errors;
- обязательны connect/read timeout;
- команда имеет уникальный `command_id`;
- mutating command не повторяется без гарантии идемпотентности;
- логируются correlation ID, operation, duration и status без secrets;
- пользователю не отдаётся raw внешний текст;
- `last_state` обновляется только при не меньшем revision;
- после reconnect запрашивается snapshot;
- frontend получает внутренние события.

Перед чтением, command, WebSocket и stop:

- пользователь имеет роль `operator`;
- session принадлежит текущему operator;
- status session допускает операцию.

Admin не управляет установкой от имени operator в MVP.

## 10. Frontend: слои

```text
app -> pages -> widgets -> features -> entities -> shared
```

Не импортируй вверх по слоям.

### Server state

TanStack Query хранит:

- current user;
- operators и login history;
- simulator catalog;
- session metadata;
- REST snapshot.

Не дублируй это в Zustand.

### Client state

Zustand допустим для:

- access token в памяти;
- локального UI-state;
- connection status;
- pending command IDs.

Не сохраняй tokens в `localStorage` или `sessionStorage`.

### API

- Все HTTP-вызовы идут через `shared/api`.
- Не вызывай `fetch` из page/component.
- 401 и refresh обрабатываются централизованно.
- Не запускай параллельно несколько refresh.
- Failed refresh завершает frontend session.
- Ошибки преобразуются в единый frontend error type.
- Во frontend нет клиента внешнего simulation API.

### Routing

```text
/login
/admin/operators
/admin/operators/:operatorId
/operator/simulators
/operator/simulators/:simulatorId
/operator/sessions/:sessionId
```

Route guard улучшает UX, но backend остаётся источником истины.

## 11. Frontend: симулятор

SVG-компоненты не рассчитывают процесс и не меняют authoritative state самостоятельно.

Команда пользователя:

1. Сгенерировать UUID `command_id`.
2. Добавить command в pending.
3. Отправить REST command.
4. При rejected убрать pending и показать ошибку.
5. При accepted ждать state/event.
6. После snapshot/patch обновить SVG.
7. Блокировать дубликат, пока command pending.
8. После timeout не менять оборудование локально.

WebSocket:

- показывать connection status;
- bounded exponential reconnect;
- после reconnect получать REST snapshot;
- очищать socket и timers при unmount;
- игнорировать события старой session;
- игнорировать revision меньше текущей;
- неизвестный event безопасно игнорировать после логирования;
- malformed payload не ломает страницу.

Accessibility:

- label каждой кнопки;
- состояние не только цветом;
- keyboard support;
- текстовое описание SVG;
- alarms и errors доступны screen reader.

## 12. Ошибки

Формат:

```json
{
  "error": {
    "code": "OPERATOR_NOT_FOUND",
    "message": "Оператор не найден",
    "details": {}
  }
}
```

Коды:

- `400` invalid operation;
- `401` unauthenticated;
- `403` forbidden;
- `404` not found;
- `409` conflict/stale revision/duplicate;
- `422` validation;
- `502` upstream protocol/failure;
- `503` simulation unavailable;
- `504` simulation timeout.

Не возвращай stack trace и внутренние URL.

## 13. Тесты

Каждая задача включает тесты соответствующего уровня.

### Backend

- unit tests security/helpers/mapping;
- service tests use cases;
- API tests с dependency override;
- PostgreSQL integration tests для constraints/JSONB;
- fake gateway вместо реального simulation service;
- WebSocket auth/event tests.

Не заменяй PostgreSQL SQLite, если тест зависит от PostgreSQL-семантики.

### Frontend

- component tests;
- feature tests через MSW;
- route guard tests;
- pending/rejected/reconnect tests;
- accessibility assertions.

### E2E

- admin создаёт operator;
- operator входит;
- открывает boiler simulator;
- запускает pump;
- получает authoritative state;
- завершает session.

E2E не зависит от реального simulation service.

## 14. Проверки качества

Backend:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Python:

- type hints публичных функций;
- `Any` только при обосновании;
- без mutable defaults;
- injectable clock/generator там, где это упрощает тесты.

Frontend:

```bash
npm run lint
npm run typecheck
npm run test
npm run build
```

TypeScript:

- `strict: true`;
- не использовать `any`;
- `unknown` сначала валидируется;
- без необоснованного non-null assertion;
- явные props/response types;
- сложная логика вынесена из JSX.

## 15. Контракты и документация

При изменении локального API:

- обнови OpenAPI;
- обнови frontend types/client;
- обнови contract tests;
- обнови README при изменении потока или конфигурации.

При изменении simulation integration:

- обнови `contracts/simulation-api/openapi.yaml`;
- обнови `websocket-events.md`;
- добавь примеры payload;
- обнови mapping tests;
- укажи необходимость согласования со вторым разработчиком.

Не меняй внешний контракт только внутри gateway.

## 16. Запрещённые решения без отдельного решения команды

- Redux вместе с Zustand;
- Axios вместе с fetch/openapi-fetch;
- синхронный SQLAlchemy engine;
- raw SQL в endpoint;
- Redis/Celery без реальной задачи;
- внутренние микросервисы;
- GraphQL;
- Kubernetes;
- Unity/Ren'Py;
- BPMN;
- WebSocket для CRUD;
- optimistic update установки;
- универсальный renderer до второго типа установки.

## 17. Порядок работы Codex

1. Прочитать задачу и документы.
2. Исследовать текущий код.
3. Составить краткий план.
4. Реализовать ограниченный вертикальный срез.
5. Добавить/обновить тесты.
6. Запустить проверки.
7. Исправить вызванные изменением ошибки.
8. В отчёте указать:
   - что изменено;
   - принятые решения;
   - выполненные команды;
   - результаты тестов;
   - оставшиеся ограничения и внешние зависимости.

Не утверждай, что тесты прошли, если они не запускались. Не делай commit/push без прямой команды пользователя.

## 18. Definition of Done изменения

- требования выполнены;
- граница simulation service не нарушена;
- auth/RBAC проверены на backend;
- миграция есть при изменении БД;
- API и DTO типизированы;
- ошибки нормализованы;
- тесты добавлены;
- checks проходят или честно указана причина;
- документация обновлена;
- secrets, temporary passwords и персональные данные не попали в логи.
Прочитай AGENTS.md и README.md целиком. Изучи текущее содержимое репозитория. Пока ничего не изменяй.

Подготовь план MVP:
1. текущее состояние репозитория;
2. предлагаемое дерево каталогов;
3. последовательность вертикальных этапов;
4. модели БД;
5. REST и WebSocket endpoints;
6. граница с внешним simulation service;
7. основные риски;
8. решения, уже зафиксированные документами.

Отдельно подтверди, что физическая логика и моделирование установки не будут реализованы в этом репозитории. Перечисли файлы первого технического шага.