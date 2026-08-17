# AI deployment and configuration

Этот файл описывает конфигурацию AI-контура MVP и фиксирует решения Этапа 15.

## Что уже было реализовано до Этапа 15

К началу этапа в проекте уже существовали:

- отдельный `ai-service` в `docker-compose.yml`;
- healthcheck AI-service;
- `AI_GATEWAY_MODE=mock|http`;
- адрес AI-service и HTTP timeouts application backend;
- отдельный короткий timeout realtime prediction;
- пути к CatBoost model и metadata;
- OpenAI-compatible LLM configuration;
- volume `./ai-service/models:/app/models`;
- `.gitignore`, исключающий `.env` и локальные секреты.

Поэтому эти части не дублировались и не переименовывались только ради соответствия названиям из исходной декомпозиции.

## Что добавлено на Этапе 15

### Независимый запуск backend от AI-service

`backend` больше не имеет `depends_on: ai-service: condition: service_healthy`.

Это принципиально для fail-open архитектуры: если AI-service не поднялся или временно unhealthy, application backend, цифровой двойник, команды оператора и deterministic assessment всё равно должны стартовать и работать.

AI-service остаётся обычным сервисом compose и при доступности подключается через HTTP gateway.

### Глобальный feature flag

```env
AI_ENABLED=true
```

- `true` — realtime AI gateway подключается к server-side telemetry collector;
- `false` — realtime prediction полностью исключается из collector, но симуляция и assessment продолжают работать;
- debrief при отключённом AI использует существующий deterministic/mock fallback и не обращается к внешнему AI-service.

Для локальной разработки без внешнего AI можно использовать либо:

```env
AI_ENABLED=false
```

либо контрактный режим:

```env
AI_ENABLED=true
AI_GATEWAY_MODE=mock
```

Для реального AI-service:

```env
AI_ENABLED=true
AI_GATEWAY_MODE=http
AI_SERVICE_BASE_URL=http://ai-service:8090
```

## Соответствие переменных исходной декомпозиции

В плане Этапа 15 использовались концептуальные названия. В коде сохранены уже существующие более явные имена:

| План | Текущая конфигурация |
| --- | --- |
| `AI_SERVICE_URL` | `AI_SERVICE_BASE_URL` |
| `AI_SERVICE_CONNECT_TIMEOUT` | `AI_CONNECT_TIMEOUT_SECONDS` |
| `AI_SERVICE_READ_TIMEOUT` | `AI_READ_TIMEOUT_SECONDS` |
| `AI_ENABLED` | `AI_ENABLED` |
| `MODEL_PATH` | `AI_RISK_MODEL_PATH` |
| `MODEL_VERSION` | хранится в metadata модели и возвращается самой моделью |
| `LLM_PROVIDER` | `AI_LLM_MODE` (`disabled` / `openai_compatible`) |
| `LLM_BASE_URL` | `AI_LLM_BASE_URL` |
| `LLM_MODEL` | `AI_LLM_MODEL` |
| `RAG_ENABLED` | `RAG_ENABLED` |

`MODEL_VERSION` намеренно не задаётся отдельной env-переменной: версия является частью metadata обученного артефакта. Это уменьшает риск рассинхронизации между файлом модели и вручную указанной версией окружения.

## ML configuration

```env
AI_RISK_MODEL_PATH=/app/models/risk-catboost-v1.cbm
AI_RISK_MODEL_METADATA_PATH=/app/models/risk-catboost-v1.json
```

Модели монтируются в контейнер:

```text
./ai-service/models -> /app/models
```

Если модель отсутствует, AI-service остаётся healthy и возвращает явный `risk-model-unavailable-v1`; отсутствие модели не делает сервис или тренажёр неработоспособными.

## LLM configuration

По умолчанию LLM выключена:

```env
AI_LLM_MODE=disabled
```

Для OpenAI-compatible endpoint:

```env
AI_LLM_MODE=openai_compatible
AI_LLM_BASE_URL=http://host.docker.internal:11434/v1
AI_LLM_MODEL=qwen2.5:7b-instruct
AI_LLM_API_KEY=
AI_LLM_TIMEOUT_SECONDS=30
AI_LLM_TEMPERATURE=0.2
```

LLM не участвует в command path и не влияет на authoritative state или deterministic assessment.

## RAG

```env
RAG_ENABLED=false
```

Флаг уже присутствует в конфигурации, но retrieval pipeline в MVP намеренно не реализован. Это точка расширения для следующего этапа после MVP: технологические регламенты → chunks → embeddings → vector store → retrieval → LLM explanation с source references.

Включение `RAG_ENABLED=true` до реализации retrieval само по себе не добавляет RAG-функциональность.

## Секреты

Настоящие значения нельзя хранить в Git:

```text
JWT_SECRET
SIMULATION_API_KEY
AI_LLM_API_KEY
POSTGRES_PASSWORD
E2E_*_PASSWORD
```

`.gitignore` исключает `.env` и `.env.*`, кроме `.env.example`. В `.env.example` должны находиться только безопасные локальные placeholders.

## Рекомендуемые режимы

Локальная разработка без AI:

```env
AI_ENABLED=false
AI_LLM_MODE=disabled
RAG_ENABLED=false
```

Разработка frontend/backend с контрактной заглушкой:

```env
AI_ENABLED=true
AI_GATEWAY_MODE=mock
AI_LLM_MODE=disabled
```

Демонстрация с ML:

```env
AI_ENABLED=true
AI_GATEWAY_MODE=http
AI_SERVICE_BASE_URL=http://ai-service:8090
AI_LLM_MODE=disabled
RAG_ENABLED=false
```

Демонстрация с ML + LLM debrief:

```env
AI_ENABLED=true
AI_GATEWAY_MODE=http
AI_LLM_MODE=openai_compatible
RAG_ENABLED=false
```

## Критерий готовности Этапа 15

Этап считается закрытым, если:

1. compose поднимает `ai-service` как отдельный компонент;
2. backend может стартовать и работать при недоступном AI-service;
3. AI можно целиком отключить feature flag без изменения кода;
4. realtime prediction имеет отдельный короткий timeout;
5. модель и LLM настраиваются через environment;
6. RAG явно выключен для MVP и имеет конфигурационную точку расширения;
7. секреты не коммитятся в Git.
