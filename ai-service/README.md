# KTC AI Service

Отдельный AI-сервис компьютерного тренажёра. Он не управляет установкой и не является источником истины по технологическому процессу.

Сервис решает две независимые задачи:

1. прогнозирует риск ошибки оператора на коротком горизонте по telemetry/action history;
2. формирует человекочитаемые объяснения и debrief по уже проверенным assessment-фактам.

RAG по технологическим регламентам предусмотрен как следующий этап после MVP, но retrieval pipeline в текущей версии не реализован.

## Граница ответственности

```text
ktc_backend
  → физика и authoritative process state

application backend
  → сессии, timeline, deterministic assessment, operator profile, scenario recommendation

ai-service
  → ML risk prediction + LLM explanation
```

AI-service **не должен**:

- рассчитывать параметры установки вместо цифрового двойника;
- отправлять команды оборудованию;
- определять фактическую ошибку вместо rules engine;
- менять итоговый score;
- самостоятельно выбирать следующий scenario code;
- принимать решения по промышленной безопасности.

## API

### Health

```http
GET /health
```

Возвращает `200`, если процесс AI-service жив. Отсутствие обученной CatBoost-модели не делает healthcheck отрицательным.

### Risk prediction

```http
POST /v1/predict-risk
```

MVP target:

```text
ERROR_IN_NEXT_10_SECONDS = 0 / 1
```

Ответ содержит:

```text
risk
predicted_error_code
horizon_seconds
model_version
features[]
```

Если модель не найдена, сервис возвращает безопасный fallback:

```text
model_version = risk-model-unavailable-v1
risk = 0
```

Это не интерпретируется как «оператор точно не ошибётся» — это явный признак отсутствующей ML-модели.

### Error explanation

```http
POST /v1/explain-error
```

На вход получает уже классифицированную ошибку и структурированный контекст. LLM только формулирует объяснение и учебную рекомендацию.

### Debrief

```http
POST /v1/debrief
```

На вход получает итоговые assessment-факты, ошибки, reaction metrics и metadata сценария.

Если application backend уже выбрал `recommended_scenario_code`, LLM может только вернуть это же значение. Выбор сценария не делегируется языковой модели.

### Recommendation contract

```http
POST /v1/recommend-training
```

Контракт сохранён как точка расширения AI-рекомендаций. В текущем MVP фактический выбор активного сценария выполняется application backend детерминированно по skill/error profile и metadata сценариев.

## Структура

```text
ai-service/
├── README.md
├── ML_RISK_MODEL_RUNBOOK.md
├── Dockerfile
├── pyproject.toml
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   ├── schemas/
│   ├── features/
│   ├── prediction/
│   ├── explanation/
│   ├── recommendations/
│   ├── llm/
│   └── rag/
├── scripts/
│   ├── generate_dataset.py
│   └── train_risk_model.py
├── datasets/
├── models/
└── tests/
```

`rag/` является архитектурным placeholder. Наличие директории и `RAG_ENABLED` не означает, что RAG уже работает.

## Risk features

Текущий feature contract включает:

```text
current_pressure
pressure_delta_5s
pressure_delta_10s
current_temperature
temperature_delta_10s
oil_flow_after_pumps
oil_flow_to_elou
oil_elou_flow_gap
pump_h1a
pump_h1b
pump_h1c
pump_nd1
pump_nd2
pump_h3
valve_kr1
valve_kr6
valve_kr7
valve_kr8
regulator_frc404
regulator_frc405
regulator_frc406
regulator_frc407
regulator_frc408
nd1_flow
nd1_target
nd1_setpoint_error
nd2_flow
nd2_setpoint_error
water_flow
e1_level
e1_ready
e1_voltage
po1_level
combined_scenario
recent_action_h1c
recent_action_nd1
recent_action_kr1
recent_action_kr6
recent_action_frc404
recent_action_frc407
recent_action_nd2
recent_action_frc408
recent_action_e1_voltage
recent_action_kr7
recent_action_kr8
last_setpoint_nd1
last_setpoint_frc404
last_setpoint_frc407
last_setpoint_nd2
last_setpoint_frc408
active_alarm_count
time_since_alarm_s
time_since_last_action_s
action_count_last_10s
scenario_step
previous_errors_total
previous_late_action_count
previous_wrong_action_count
previous_wrong_sequence_count
previous_missed_action_count
```

Текущие sensor bindings:

```text
pressure    → PRA1, fallback PRA351
temperature → TR2, fallback TR41_1/TR1
oil flow    → FQR117_1/FQR117_2/FQR117_3/FQR118
ELOU        → process.elou: FRC407/FRC408/ND2/H3/E1/KR7/KR8/PO1
```

Перед обучением на реальном KTC необходимо проверить, что актуальная версия `ktc_backend` действительно передаёт эти signals с ожидаемой семантикой и единицами.

Feature extraction строится только из информации с timestamp `<= prediction time`. Future actions/errors в признаки не попадают.

## Модель

Рекомендуемый MVP classifier — CatBoost для табличных признаков.

По умолчанию service ожидает:

```env
AI_RISK_MODEL_PATH=/app/models/risk-catboost-v2.cbm
AI_RISK_MODEL_METADATA_PATH=/app/models/risk-catboost-v2.json
```

Metadata фиксирует:

- `model_version`;
- target/horizon;
- threshold;
- ordered `feature_names`;
- global feature importance;
- training/validation row counts;
- random seed;
- provenance.

При загрузке feature names из metadata должны точно совпасть с текущим кодовым contract. Это защита от тихого использования несовместимой модели.

## Как собрать данные и обучить модель

Полная инструкция: `ML_RISK_MODEL_RUNBOOK.md`.

Краткая цепочка:

```text
PostgreSQL / simulation_events / operator_errors
        ↓
backend exporter
        ↓
session_exports.jsonl
        ↓
generate_dataset.py
        ↓
risk.csv
        ↓
train_risk_model.py
        ↓
risk-catboost-v2.cbm + risk-catboost-v2.json
```

### 1. Экспорт сессий

Из корня backend:

```bash
cd backend
python -m app.commands.export_ml_sessions --output /tmp/session_exports.jsonl
```

Экспорт должен содержать snapshots, operator actions, фактические assessment errors, scenario code и **исторический** профиль ошибок, рассчитанный только по предыдущим сессиям.

### 2. Dataset

```bash
cd ../ai-service
python -m scripts.generate_dataset /tmp/session_exports.jsonl datasets/risk.csv
```

Каждая строка соответствует prediction point. Target равен 1, если ошибка происходит в интервале `(now, now + 10s]`.

### 3. Training

```bash
python -m scripts.train_risk_model datasets/risk.csv
```

Trainer разделяет данные по `session_id`, чтобы строки одной сессии не оказались одновременно в train и validation.

### 4. Deployment

Файлы модели положить в:

```text
ai-service/models/
```

При Docker Compose директория монтируется в `/app/models`.

После замены модели процесс AI-service нужно перезапустить: predictor lazy-loads artifact один раз на процесс.

## LLM

По умолчанию:

```env
AI_LLM_MODE=disabled
```

В этом режиме explanation/debrief работают через deterministic fallback.

Для OpenAI-compatible API:

```env
AI_LLM_MODE=openai_compatible
AI_LLM_BASE_URL=http://host.docker.internal:11434/v1
AI_LLM_MODEL=qwen2.5:7b-instruct
AI_LLM_API_KEY=
AI_LLM_TIMEOUT_SECONDS=30
AI_LLM_TEMPERATURE=0.2
```

Можно использовать локальный или внешний OpenAI-compatible endpoint.

Prompts ограничивают модель структурированными фактами: запрещено изменять error classification, score и придумывать технологические требования, которых нет во входе.

При timeout/protocol error используется deterministic fallback.

## RAG — после MVP

```env
RAG_ENABLED=false
```

План расширения:

```text
source document
→ chunking
→ embeddings
→ vector store
→ retrieval по error/process context
→ LLM
→ explanation + source references
```

Назначение RAG — не «учить LLM физике установки», а давать проверяемое основание для объяснения:

```text
что произошло
+ почему это считается ошибкой
+ на какой раздел/страницу регламента можно сослаться
```

В ответах должны сохраняться `source_id`, раздел/страница и релевантный фрагмент/метаданные источника.

## Локальный запуск

```bash
cd ai-service
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8090
```

Проверка:

```bash
curl http://localhost:8090/health
```

Через compose сервис доступен application backend по адресу:

```text
http://ai-service:8090
```

## Docker

Образ собирается из `ai-service/Dockerfile`.

Модели не вшиваются в Git как обязательные артефакты; compose монтирует:

```text
./ai-service/models:/app/models
```

Это позволяет менять versioned model artifact без изменения application code.

## Тесты

```bash
cd ai-service
pytest
```

Тесты покрывают:

- API contracts;
- feature extraction;
- отсутствие future leakage;
- dataset target generation;
- predictor fallback при отсутствии модели;
- LLM disabled fallback;
- OpenAI-compatible narrative contract.

Полная test matrix всей системы находится в `../AI_TESTING.md`.

## Fail-open

AI-service не должен находиться в command path.

Если он недоступен:

- operator commands продолжают уходить в simulation service;
- authoritative telemetry продолжает собираться;
- deterministic assessment продолжает работать;
- frontend показывает состояние AI unavailable;
- application backend пишет audit error/timeout.

## Что не хранить в Git

Не коммитировать:

- реальные `.env`;
- API keys;
- производственные datasets;
- большие `.cbm` artifacts без отдельного решения по model registry/artifact storage;
- документы с ограниченным доступом для будущего RAG.

## Статус MVP

Код prediction/explanation/debrief готов к подключению реальных артефактов. Для фактического ненулевого ML prediction требуется обученная модель, построенная на репрезентативных траекториях цифрового двойника. До этого сервис корректно работает в `risk-model-unavailable`/mock режиме.
