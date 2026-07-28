# CODEX_PROMPTS.md

Промпты выполняются по одному. После каждого шага нужно просмотреть diff и результаты тестов. Каждый промпт предполагает наличие `README.md` и `AGENTS.md` в корне.

## 0. Аудит и план без изменений

```text
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
```

## 1. Каркас monorepo

```text
Прочитай AGENTS.md и README.md. Создай только каркас monorepo, без auth и предметных endpoint.

Нужно:
- backend FastAPI на Python 3.12+ с pyproject.toml и uv;
- frontend React + TypeScript strict + Vite;
- PostgreSQL в docker-compose.yml;
- Dockerfile для backend/frontend;
- .env.example;
- GET /health/live;
- GET /health/ready с проверкой БД;
- базовые JSON-логи backend;
- CORS из конфигурации;
- SQLAlchemy async session;
- Alembic;
- Ruff, mypy, pytest;
- ESLint, typecheck, Vitest;
- минимальный frontend layout;
- понятные команды запуска и проверок.

Не реализуй пользователей, auth, simulator, mock процесса или физическую модель.

Добавь минимальные тесты health endpoint и рендера frontend. Запусти доступные lint/typecheck/tests/build. В отчёте перечисли созданные файлы и команды.
```

## 2. Модели БД и миграции

```text
Прочитай AGENTS.md и README.md. Реализуй backend-модели и Alembic migrations:
- User;
- RefreshToken;
- LoginEvent;
- SimulatorDefinition;
- SimulationSession;
- SimulationCommand.

Требования:
- UUID primary keys;
- timezone-aware UTC;
- role enum admin/operator;
- is_active вместо удаления user;
- unique username;
- foreign keys, constraints и индексы;
- JSONB только по README;
- upgrade/downgrade;
- CLI create_admin без hardcoded password;
- CLI seed_simulators, идемпотентно создающая boiler-demo;
- secrets и temporary passwords не логируются.

Создай repositories только под реальные use cases, без generic repository. Добавь PostgreSQL-aware tests constraints, seed idempotency и create_admin.

Пока не добавляй HTTP auth и simulation integration. Запусти backend checks.
```

## 3. Auth, refresh rotation и RBAC

```text
Прочитай AGENTS.md и README.md. Реализуй auth vertical slice.

Endpoints:
- POST /api/v1/auth/login;
- POST /api/v1/auth/refresh;
- POST /api/v1/auth/logout;
- GET /api/v1/auth/me.

Требования:
- username + password;
- Argon2 через pwdlib;
- короткоживущий access JWT в JSON;
- refresh token только в HttpOnly cookie;
- hash refresh token в БД;
- rotation и revoke;
- logout;
- inactive user не может login/refresh;
- generic login error;
- LoginEvent для success/failure;
- безопасное извлечение IP/User-Agent;
- единый API error format;
- dependencies current_user, require_admin, require_operator;
- не доверять role из request body.

Тесты:
- success login;
- invalid password;
- unknown username с тем же внешним ответом;
- inactive user;
- login events;
- refresh rotation;
- reuse старого refresh token;
- logout;
- /me;
- role dependencies.

Не реализуй operator CRUD и simulator integration. Запусти checks.
```

## 4. Управление операторами

```text
Прочитай AGENTS.md и README.md. Реализуй backend-модуль управления операторами.

Endpoints:
- GET /api/v1/operators;
- POST /api/v1/operators;
- GET /api/v1/operators/{operator_id};
- PATCH /api/v1/operators/{operator_id};
- POST /api/v1/operators/{operator_id}/reset-password;
- GET /api/v1/operators/{operator_id}/login-history;
- GET /api/v1/operators/{operator_id}/login-stats.

Требования:
- только admin;
- только пользователи role=operator;
- пагинация и стабильная сортировка;
- фильтры username/full_name/is_active;
- create: username, full_name, optional password;
- при отсутствии пароля генерировать стойкий временный пароль;
- пароль вернуть только один раз;
- password не логировать;
- duplicate username -> 409;
- PATCH меняет только разрешённые поля;
- деактивация отзывает refresh tokens;
- stats: successful_count и last_successful_login_at;
- history: дата, success, failure_reason, IP, User-Agent;
- не отдавать password_hash/token data.

Добавь service/repository/API tests и RBAC tests. Не создавай frontend и не касайся simulation service. Запусти checks.
```

## 5. Контракт и SimulationGateway

```text
Прочитай AGENTS.md и README.md. Реализуй контракт и integration layer без физической модели.

Создай:
- contracts/simulation-api/openapi.yaml;
- contracts/simulation-api/websocket-events.md;
- примеры payload;
- internal DTO: SimulationState, EquipmentState, Alarm, CommandResult, SimulationEvent;
- SimulationGateway Protocol;
- HttpSimulationGateway;
- MockSimulationGateway;
- factory по SIMULATION_GATEWAY_MODE;
- типизированные integration errors;
- mapping внешних enum/payload во внутренние DTO;
- config URL/API key/timeouts.

Операции:
- create_session;
- get_state;
- send_command;
- stop_session;
- stream_events.

MockSimulationGateway:
- fixture котла и двух насосов;
- start/stop для steam_supply_pump и steam_exhaust_pump;
- меняет только status выбранного насоса;
- не рассчитывает temperature/pressure/flow;
- может вернуть rejected, timeout, malformed payload;
- выдаёт нормализованные events.

HttpSimulationGateway:
- httpx;
- Pydantic validation;
- внешние exceptions не выходят из integration layer;
- нет опасного automatic retry команды;
- command_id как idempotency key;
- API key не логируется.

Добавь contract/mapping/error/mock tests. Не создавай session REST endpoints и frontend WebSocket relay.
```

## 6. Backend сессий и команд

```text
Прочитай AGENTS.md и README.md. Через SimulationGateway реализуй backend vertical slice.

Endpoints:
- GET /api/v1/simulators;
- GET /api/v1/simulators/{simulator_id};
- POST /api/v1/simulation-sessions;
- GET /api/v1/simulation-sessions/{session_id};
- GET /api/v1/simulation-sessions/{session_id}/state;
- POST /api/v1/simulation-sessions/{session_id}/commands;
- POST /api/v1/simulation-sessions/{session_id}/stop;
- WS /ws/v1/simulation-sessions/{session_id}.

Требования:
- только active operator;
- ownership локальной session;
- admin не управляет session;
- create: local status creating -> external create -> active/failed;
- command сначала сохраняется pending;
- whitelist:
  - steam_supply_pump: start/stop;
  - steam_exhaust_pump: start/stop;
- accepted/rejected/failed сохраняются;
- HTTP accepted не меняет state;
- last_state обновляется авторитетным snapshot при revision >= текущего;
- WebSocket транслирует только нормализованные events;
- WebSocket не допускает чужую session;
- stop идемпотентен для завершённой session;
- integration errors преобразуются в согласованные API errors;
- внешний stream корректно закрывается.

Тесты:
- catalog;
- create session;
- ownership;
- accepted/rejected/timeout;
- invalid command;
- stale revision;
- stop;
- WebSocket auth/relay/disconnect cleanup.

Не реализуй frontend и физическую модель.
```

## 7. Frontend foundation и auth

```text
Прочитай AGENTS.md и README.md. Реализуй frontend foundation и auth flow.

Нужно:
- Material UI app shell;
- React Router;
- TanStack Query provider;
- Zustand auth store только для access token/client state;
- typed shared API client;
- singleton refresh flow без параллельных refresh;
- access token только в памяти;
- credentials include для refresh cookie;
- /login;
- role-based redirects;
- protected routes;
- GET /auth/me bootstrap;
- logout;
- ErrorView/LoadingView;
- русские сообщения;
- responsive layout и базовая accessibility.

Маршруты placeholders:
- /admin/operators;
- /operator/simulators.

Добавь MSW handlers и tests:
- successful/invalid login;
- bootstrap through refresh;
- admin/operator redirect;
- failed refresh -> logout;
- forbidden route.

Запусти lint, typecheck, tests и build.
```

## 8. Интерфейс администратора

```text
Прочитай AGENTS.md и README.md. Реализуй frontend admin module.

Страницы:
- /admin/operators;
- /admin/operators/:operatorId.

Список:
- username, full_name, active status;
- successful login count;
- last successful login;
- pagination;
- text и active filters;
- создание оператора.

Создание:
- username/full_name/optional password;
- сгенерированный password показать один раз в modal;
- предупреждение о безопасной передаче;
- не писать password в console/storage.

Карточка:
- сведения;
- active toggle с подтверждением;
- reset password;
- временный password показать один раз;
- metric cards successful_count/last login;
- login history table;
- empty/loading/error states.

Используй TanStack Query, React Hook Form, Zod и MUI. Добавь MSW tests create/conflict/deactivate/reset/history/RBAC.

Не добавляй статистику действий в тренажёре: только логины.
```

## 9. Каталог и запуск сессии

```text
Прочитай AGENTS.md и README.md. Реализуй operator flow до визуального тренажёра.

Страницы:
- /operator/simulators;
- /operator/simulators/:simulatorId;
- /operator/sessions/:sessionId как placeholder.

Требования:
- загрузить active simulator definitions;
- карточка «Котёл с двумя насосами»;
- описание и availability;
- «Начать тренировку» -> POST /simulation-sessions;
- защита от двойного создания;
- redirect в session route;
- UI для unavailable/timeout/protocol error;
- operator не видит admin navigation;
- admin не входит в operator flow;
- refresh session route восстанавливает metadata через GET.

Добавь tests и запусти frontend checks.
```

## 10. SVG-тренажёр котла

```text
Прочитай AGENTS.md и README.md. Реализуй /operator/sessions/:sessionId и SVG-визуализацию.

Показать:
- котёл;
- steam_supply_pump;
- steam_exhaust_pump;
- линии потока;
- temperature и pressure;
- session status;
- alarms;
- WebSocket connection status;
- журнал последних команд.

Команды:
- start/stop обоих насосов.

Поток:
- загрузить session и REST snapshot;
- подключиться к backend WebSocket;
- валидировать events;
- поддержать state.snapshot/state.patch;
- command.accepted/rejected;
- alarm.raised/cleared;
- integration.error;
- хранить revision и игнорировать меньший;
- bounded exponential reconnect;
- после reconnect запросить snapshot;
- cleanup socket/timers;
- command_id генерировать на клиенте;
- pending блокирует дубликат;
- HTTP accepted не переключает насос локально;
- состояние меняется только после authoritative state;
- rejected/timeout отображаются;
- stop завершает session и возвращает в catalog.

Не рассчитывай физические параметры и зависимости между ними.

Тесты:
- initial snapshot;
- accepted остаётся pending до state;
- rejected;
- duplicate protection;
- revision;
- reconnect + snapshot;
- alarm;
- malformed/unknown event;
- stop;
- keyboard accessibility.

Запусти checks и build.
```

## 11. E2E и стабилизация

```text
Прочитай AGENTS.md и README.md. Не добавляй новые product features. Стабилизируй MVP.

Нужно:
- docker-compose для frontend/backend/PostgreSQL;
- SIMULATION_GATEWAY_MODE=mock;
- deterministic fixtures;
- Playwright E2E:
  1. test setup создаёт admin;
  2. admin входит;
  3. создаёт operator;
  4. operator входит;
  5. login history обновляется;
  6. operator открывает boiler-demo;
  7. запускает steam_supply_pump;
  8. UI получает authoritative running state;
  9. останавливает pump;
  10. завершает session;
- refresh страницы active session;
- forbidden routes;
- simulation unavailable;
- проверка отсутствия secrets/passwords в логах;
- readiness ожидание сервисов;
- без flaky sleeps, только ожидание состояния/event;
- README с фактическими командами запуска.

Запусти полный backend/frontend/E2E набор. Явно укажи, что не удалось запустить.
```

## 12. Финальный code review

```text
Прочитай AGENTS.md и README.md. Проведи финальный review MVP без новых функций.

Проверь:
- отсутствие физической логики в frontend/backend/mock;
- frontend не вызывает simulation service;
- integration только через SimulationGateway;
- внешний payload не попадает в frontend;
- backend auth/RBAC и ownership;
- admin не управляет установкой;
- refresh token защищён и ротируется;
- secrets/passwords не логируются;
- state меняется только по authoritative events/snapshot;
- stale revisions игнорируются;
- WebSocket resources закрываются;
- migrations/constraints корректны;
- contract examples соответствуют коду;
- README соответствует запуску;
- tests покрывают happy path и основные отказы.

Сначала выдай проблемы по критичности с файлами и строками. Затем исправь только подтверждённые проблемы без широкого рефакторинга. Запусти проверки и дай итоговый отчёт.
```

## Дополнительный промпт: адаптация к фактическому API второго разработчика

```text
Прочитай AGENTS.md, README.md и contracts/simulation-api. Изучи предоставленный фактический OpenAPI и примеры событий simulation service.

Не меняй внутренние frontend DTO и UI без необходимости.

Нужно:
1. таблица различий ожидаемого и фактического контрактов;
2. breaking changes;
3. обновление contracts/simulation-api;
4. адаптация только external DTO и HttpSimulationGateway;
5. сохранение стабильных SimulationGateway и normalized DTO;
6. mapping/contract tests;
7. проверка timeout, errors, idempotency и WebSocket events;
8. отсутствие физической логики;
9. отсутствие raw external payload во frontend.

Сначала покажи mapping plan, затем внеси изменения и запусти backend tests.
```
