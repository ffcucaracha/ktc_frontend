# Как запустить ML-прогноз риска полноценно

Этот документ описывает полный путь от накопления тренировочных сессий до работающего `POST /v1/predict-risk` с обученной CatBoost-моделью.

Текущая цель модели:

```text
ERROR_IN_NEXT_10_SECONDS = 0 / 1
```

То есть для каждого момента времени модель оценивает вероятность того, что в следующие 10 секунд оператор совершит ошибку, которую затем зафиксирует детерминированный assessment engine application backend.

Главный архитектурный принцип: AI-service не генерирует и не исправляет физику процесса. Телеметрия должна приходить от цифрового двойника через `ktc_backend`, а ошибки — из нашего детерминированного assessment. ML использует эти данные как обучающий материал.

---

## 1. Что уже реализовано

В проекте уже есть:

- server-side сбор телеметрии активной сессии;
- timeline с `state.snapshot`, `operator.command` и системными событиями;
- учебные сценарии и ожидаемые действия;
- детерминированный assessment;
- классификация ошибок `WRONG_ACTION`, `WRONG_SEQUENCE`, `LATE_ACTION`, `MISSED_ACTION`;
- API timeline и assessment;
- AI-service;
- feature engineering для модели риска;
- генератор табличного dataset;
- скрипт обучения CatBoost;
- runtime-загрузка модели в `/v1/predict-risk`.

Для полноценной работы ML не хватает прежде всего достаточного количества размеченных тренировочных сессий и удобного экспорта этих сессий в формат, который принимает `generate_dataset.py`.

---

## 2. Общий pipeline

```text
ktc_backend
    ↓
телеметрия цифрового двойника
    ↓
FastAPI application backend
    ↓
simulation_events + operator_errors + training_results
    ↓
экспорт тренировочных сессий в JSONL
    ↓
generate_dataset.py
    ↓
risk.csv
    ↓
train_risk_model.py
    ↓
risk-catboost-v1.cbm
risk-catboost-v1.json
    ↓
ai-service
    ↓
POST /v1/predict-risk
```

---

# 3. Шаг 1. Накопить тренировочные сессии

Для обучения нужны не отдельные snapshots, а целые тренировочные сессии.

Каждая полезная сессия должна содержать:

- `session_id`;
- `scenario_code`;
- последовательность `state.snapshot`;
- действия оператора;
- итоговые ошибки assessment;
- предыдущую историю ошибок оператора, если она доступна.

Лучше собирать данные по нескольким существующим сценариям блока подогрева нефти:

```text
oil-heating-basic-startup
oil-heating-basic-shutdown
oil-heating-flow-control
oil-heating-wrong-sequence-training
oil-heating-reaction-time-training
```

Нужны как правильные, так и ошибочные прохождения.

Если собрать только ошибочные тренировки, модель не научится различать нормальное состояние и риск. Если собрать только идеальные — положительного класса `ERROR_IN_NEXT_10_SECONDS=1` практически не будет.

## Какие ошибки полезно специально воспроизводить

Для текущей версии модели можно получать размеченные сессии следующими способами:

### Нормальное прохождение

Оператор выполняет сценарий в правильном порядке и в допустимые временные интервалы.

Ожидаемый результат:

```text
нет ошибок
```

Это основной источник отрицательного класса `target=0`.

### Задержка действия

Например, в `oil-heating-reaction-time-training` оператор ждёт больше разрешённых 5 секунд перед следующим действием.

Assessment должен сформировать:

```text
LATE_ACTION
```

### Неправильная последовательность

Например, вместо:

```text
H1A → H1B → H1V
```

выполнить:

```text
H1B → H1A → H1V
```

Assessment должен сформировать:

```text
WRONG_SEQUENCE
```

### Неверное действие / setpoint

В `oil-heating-flow-control` установить FRC вне разрешённого диапазона сценария.

Assessment должен сформировать:

```text
WRONG_ACTION
```

### Пропущенное действие

Завершить сессию до выполнения обязательного шага.

Assessment должен сформировать:

```text
MISSED_ACTION
```

Важно: мы не добавляем искусственные датчики, аварии или технологические зависимости в AI-service. Если понадобится моделировать новые физические отклонения, они должны появиться в цифровом двойнике.

---

# 4. Сколько данных нужно

Текущий training script технически разрешает обучение от 20 строк dataset, но это только защита от совсем пустого входа и не является рекомендацией по качеству модели.

Для демонстрационного MVP разумная первая цель:

```text
50–100 тренировочных сессий
```

из них желательно иметь:

```text
20–40% с ошибками
60–80% без ошибок или с участками до ошибки
```

Одна сессия даёт много временных строк, потому что dataset строится по каждому snapshot.

Более важен не абсолютный объём строк, а разнообразие независимых сессий. 10 000 окон из одной и той же тренировки хуже, чем несколько тысяч окон из десятков разных прохождений.

Для соревнования можно начать с меньшего количества, но метрики в таком случае следует честно обозначать как результаты на синтетически/контролируемо собранном демонстрационном наборе, а не как промышленную валидацию.

---

# 5. Шаг 2. Получить итоговый assessment

После прохождения сессии assessment должен быть рассчитан.

Application backend предоставляет:

```text
GET  /api/v1/simulation-sessions/{session_id}/assessment
POST /api/v1/simulation-sessions/{session_id}/assessment
GET  /api/v1/simulation-sessions/{session_id}/errors
GET  /api/v1/simulation-sessions/{session_id}/timeline
```

Перед экспортом лучше явно выполнить:

```text
POST /api/v1/simulation-sessions/{session_id}/assessment
```

чтобы ошибки соответствовали актуальному timeline.

Для законченной сессии assessment имеет финальный статус, и только тогда корректно размечаются `MISSED_ACTION`.

---

# 6. Шаг 3. Собрать session export

`ai-service/scripts/generate_dataset.py` принимает JSONL: один JSON-объект на одну строку, одна строка — одна тренировочная сессия.

Ожидаемая структура:

```json
{
  "session_id": "2dd7469d-18c5-4cba-a5f8-fc7d52c0d832",
  "scenario_code": "oil-heating-basic-startup",
  "operator_profile": {
    "previous_errors": {
      "LATE_ACTION": 2,
      "WRONG_SEQUENCE": 1
    }
  },
  "snapshots": [
    {
      "simulation_time_ms": 10000,
      "revision": 10,
      "sensors": {
        "PRA351": 4.4,
        "TR41_1": 117.5
      },
      "pumps": {
        "H1A": true,
        "H1B": false,
        "H1V": false
      },
      "regulators": {
        "FRC404": 40,
        "FRC405": 0,
        "FRC406": 0
      },
      "alarms": []
    }
  ],
  "actions": [
    {
      "simulation_time_ms": 8000,
      "equipment_id": "H1A",
      "action": "start",
      "payload": {}
    }
  ],
  "errors": [
    {
      "occurred_at_ms": 17000,
      "error_code": "LATE_ACTION"
    }
  ]
}
```

## Откуда брать поля

### snapshots

Из timeline необходимо выбрать события:

```text
state.snapshot
```

Их `payload` уже содержит состояние цифрового двойника.

Экспортер должен привести его к DTO `TelemetryPoint`:

```text
simulation_time_ms
revision
sensors
pumps
regulators
alarms
```

Если `ktc_backend` добавляет дополнительные поля, они могут храниться в timeline, но текущая бинарная модель использует только перечисленные признаки.

### actions

Из timeline выбрать:

```text
operator.command
```

Для каждого события нужны:

```text
simulation_time_ms
equipment_id
action
payload
```

### errors

Из `/assessment` или `/errors` взять ошибки assessment.

Минимально нужны:

```text
occurred_at_ms
error_code
```

В текущей модели `error_code` используется для отладки/будущего multiclass, а бинарный target определяется самим фактом ошибки в горизонте 10 секунд.

### operator_profile.previous_errors

Для первой модели поле можно заполнить историей прошлых завершённых сессий оператора.

Важно не включать в профиль ошибки из текущей или будущей сессии — иначе появится data leakage.

Если история отсутствует:

```json
{
  "previous_errors": {}
}
```

---

# 7. Что ещё желательно реализовать в application backend

На текущем этапе нет отдельного автоматического экспортера ML session export.

Рекомендуемый следующий технический шаг — небольшой backend/script exporter, который для списка завершённых session IDs:

1. читает `simulation_events`;
2. читает `operator_errors`;
3. получает `scenario_code`;
4. считает только исторические ошибки оператора до начала текущей сессии;
5. нормализует snapshots и actions;
6. записывает одну JSONL-строку на сессию.

Предлагаемый файл:

```text
backend/app/commands/export_ml_sessions.py
```

Пример будущего вызова:

```bash
python -m app.commands.export_ml_sessions \
  --output /tmp/session_exports.jsonl
```

Для MVP данные можно собрать и внешним скриптом через существующие API, но для воспроизводимого ML pipeline лучше сделать экспорт непосредственно из application backend.

---

# 8. Шаг 4. Проверить качество session export

Перед генерацией dataset проверить:

- snapshots отсортированы по `simulation_time_ms`;
- время не идёт назад;
- у snapshots есть `revision`;
- имеются реальные изменения telemetry;
- actions имеют корректные временные метки;
- ошибки относятся к этой же сессии;
- ошибки после завершения другой сессии не попали в текущую;
- `operator_profile` содержит только прошлую историю;
- есть как ошибочные, так и нормальные сессии.

Полезно отдельно посчитать:

```text
число сессий
число snapshots
число действий
число ошибок по каждому error_code
доля сессий без ошибок
средняя длительность сессии
```

---

# 9. Шаг 5. Построить табличный dataset

Из каталога `ai-service`:

```bash
python scripts/generate_dataset.py \
  datasets/session_exports.jsonl \
  datasets/risk.csv
```

Скрипт проходит по каждому snapshot текущей сессии.

Для точки времени `t` он использует только окно:

```text
[t - 10 секунд ; t]
```

и только действия с временем:

```text
action_time <= t
```

Target:

```text
target_error_next_10s = 1
```

если assessment-error произошла:

```text
t < error_time <= t + 10 секунд
```

иначе:

```text
target_error_next_10s = 0
```

Это принципиально важно: будущая ошибка используется только как label, но не как feature.

Dataset содержит служебные поля:

```text
session_id
scenario_code
simulation_time_ms
future_error_code
```

и ML features из `app/features/risk.py`.

---

# 10. Текущие features

Модель использует:

```text
current_pressure
pressure_delta_5s
pressure_delta_10s
current_temperature
temperature_delta_10s
pump_h1a
pump_h1b
pump_h1v
regulator_frc404
regulator_frc405
regulator_frc406
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

Сейчас pressure и temperature привязаны к:

```text
PRA351
TR41_1
```

Перед первым реальным обучением нужно обязательно проверить, что эти ключи действительно стабильно присутствуют в telemetry текущего `ktc_backend` и имеют нужный смысл/единицы измерения.

Если upstream contract изменится, feature extractor нужно менять осознанно и одновременно повышать версию feature/model contract.

---

# 11. Шаг 6. Проверить dataset перед обучением

Минимальные проверки:

```text
rows >= 20
target содержит 0 и 1
есть больше одной session_id
нет NaN/inf
feature columns числовые
```

Но для реальной оценки нужно дополнительно проверить class balance.

Например:

```text
target=0: 95%
target=1: 5%
```

означает сильный дисбаланс.

В такой ситуации accuracy почти бесполезна: модель, всегда предсказывающая `0`, уже получит 95% accuracy.

Для risk model важнее смотреть:

```text
ROC-AUC
PR-AUC
precision
recall
F1
confusion matrix
```

Особенно важен recall положительного класса, потому что задача модели — не пропустить приближающуюся ошибку. Но слишком низкий precision создаст постоянные ложные предупреждения оператору, поэтому threshold нужно выбирать по компромиссу precision/recall.

Текущий training script сохраняет CatBoost и metadata, но пока не формирует отдельный metrics report. Перед демонстрационным обучением рекомендуется расширить его сохранением метрик validation set.

---

# 12. Почему split делается по session_id

Нельзя делать обычный случайный row-level train/test split.

Соседние snapshots одной сессии очень похожи:

```text
t = 10s
t = 12s
t = 14s
```

Если первая строка попадёт в train, а две другие в validation, модель фактически увидит почти ту же траекторию при обучении. Метрики будут завышены.

В `train_risk_model.py` split выполняется по целому `session_id`.

То есть одна тренировочная сессия полностью находится либо в train, либо в validation.

---

# 13. Шаг 7. Обучить CatBoost

Из `ai-service`:

```bash
python scripts/train_risk_model.py datasets/risk.csv
```

По умолчанию будут созданы:

```text
models/risk-catboost-v1.cbm
models/risk-catboost-v1.json
```

Можно менять параметры:

```bash
python scripts/train_risk_model.py \
  datasets/risk.csv \
  --iterations 500 \
  --threshold 0.6
```

Текущие основные параметры:

```text
CatBoostClassifier
loss_function = Logloss
eval_metric = AUC
depth = 6
learning_rate = 0.05
random_seed = 21
early_stopping_rounds = 50
```

Training script проверяет наличие обоих классов и использует validation session split.

---

# 14. Что хранится в metadata модели

Рядом с `.cbm` сохраняется JSON:

```text
model_version
target
horizon_seconds
threshold
feature_names
feature_importances
training_rows
validation_rows
seed
data_provenance
```

AI-service при загрузке сравнивает сохранённый список `feature_names` с текущим `FEATURE_NAMES`.

Если контракт признаков изменился, старая модель не должна тихо использоваться с новым кодом.

---

# 15. Шаг 8. Подключить модель к AI-service

В `.env`:

```text
AI_RISK_MODEL_PATH=/app/models/risk-catboost-v1.cbm
AI_RISK_MODEL_METADATA_PATH=/app/models/risk-catboost-v1.json
```

`docker-compose.yml` монтирует:

```text
./ai-service/models:/app/models
```

После обучения достаточно перезапустить AI-service:

```bash
docker compose restart ai-service
```

Если зависимости/образ ещё не пересобирались после добавления CatBoost:

```bash
docker compose build ai-service
docker compose up -d ai-service
```

---

# 16. Шаг 9. Проверить inference вручную

После запуска AI-service проверить:

```text
GET /health
```

Затем отправить валидный запрос:

```text
POST /v1/predict-risk
```

Пример:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000001",
  "scenario_code": "oil-heating-basic-startup",
  "operator_profile": {
    "previous_errors": {
      "LATE_ACTION": 2
    }
  },
  "window": [
    {
      "simulation_time_ms": 10000,
      "revision": 10,
      "sensors": {
        "PRA351": 4.4,
        "TR41_1": 117.5
      },
      "pumps": {
        "H1A": true,
        "H1B": false,
        "H1V": false
      },
      "regulators": {
        "FRC404": 40,
        "FRC405": 0,
        "FRC406": 0
      },
      "alarms": []
    }
  ],
  "recent_actions": [
    {
      "simulation_time_ms": 8000,
      "equipment_id": "H1A",
      "action": "start",
      "payload": {}
    }
  ]
}
```

При загруженной модели `model_version` должен быть:

```text
risk-catboost-v1
```

Если возвращается:

```text
risk-model-unavailable-v1
```

значит `.cbm` или metadata не найдены по заданным путям.

---

# 17. Шаг 10. Подключить прогноз к живой тренировке

Сам AI endpoint уже существует, но следующий integration step — регулярно вызывать его из application backend во время активной сессии.

Рекомендуемая схема:

```text
SimulationTelemetryCollector
    ↓
последние 10 секунд snapshots
    + последние actions
    + исторический skill/error profile
    ↓
AIGateway.predict_risk()
    ↓
risk prediction
    ↓
simulation_events source=ai
    ↓
WebSocket / frontend
```

Не нужно вызывать ML на каждый sensor update, если telemetry идёт часто. Для MVP достаточно inference раз в 1–2 секунды.

Результат полезно сохранять в timeline как отдельное событие, например:

```text
ai.risk.prediction
```

с payload:

```json
{
  "risk": 0.82,
  "predicted_error_code": "ERROR_IN_NEXT_10_SECONDS",
  "horizon_seconds": 10,
  "model_version": "risk-catboost-v1",
  "features": []
}
```

Это позволит потом сравнивать прогноз с фактической ошибкой и считать качество модели на реальных тренировках.

---

# 18. Training mode и Exam mode

Прогноз можно вычислять в обоих режимах, но UI-поведение должно отличаться.

## training

Можно показать оператору предупреждение:

```text
Повышенный риск ошибки в ближайшие 10 секунд
```

При необходимости позже AI/LLM может сформулировать обучающую подсказку.

## exam

Прогноз нужно сохранять для оценки модели, но не показывать оператору до окончания экзамена.

Иначе система сама изменит поведение человека и испортит смысл экзамена.

---

# 19. Как оценивать модель после обучения

Минимальный validation report должен содержать:

```text
число train sessions
число validation sessions
число train rows
число validation rows
positive class ratio
ROC-AUC
PR-AUC
precision
recall
F1
confusion matrix
threshold
```

Отдельно желательно считать метрики по:

```text
scenario_code
error type
operator
```

Это покажет, например, что модель хорошо предсказывает `LATE_ACTION`, но почти не видит `WRONG_SEQUENCE`.

Поскольку текущий target бинарный, `future_error_code` в dataset пока не участвует в обучении. Он нужен для анализа и будущего перехода к multiclass.

---

# 20. Выбор threshold

`predict_proba` выдаёт вероятность 0..1.

Текущий default threshold:

```text
0.5
```

Его нельзя считать автоматически оптимальным.

Для обучающего тренажёра стоимость ошибок различна:

```text
false negative
модель не предупредила перед реальной ошибкой

false positive
модель предупредила, но ошибки не произошло
```

Для safety-oriented сценария допустимо снизить threshold ради recall. Для обычной учебной тренировки слишком частые false positives будут раздражать и снижать доверие.

Threshold нужно выбирать по validation set и сохранять в metadata модели.

---

# 21. Что нельзя делать при подготовке данных

Нельзя использовать как feature:

- ошибку, которая произошла после prediction timestamp;
- итоговый score текущей сессии;
- финальный assessment текущей сессии;
- future action;
- future alarm;
- future state;
- факт завершения сценария, если в момент прогноза он ещё не был известен.

Иначе возникнет data leakage и красивые метрики не перенесутся в live inference.

Также нельзя случайно смешивать snapshots одной сессии между train и validation.

---

# 22. Контроль reproducibility

Для каждого обученного artifact желательно сохранять:

```text
model_version
git commit SHA
feature contract version
dataset version / checksum
число sessions
train/validation session IDs или их manifest
random seed
CatBoost parameters
metrics
threshold
created_at
```

Большие dataset и `.cbm` уже исключены из Git. Для соревнования допустимо хранить небольшую демонстрационную модель отдельно, но нужно иметь возможность полностью воспроизвести её из session exports.

---

# 23. Минимальный путь до работающего demo

Чтобы ML заработал на демонстрации, достаточно выполнить следующий минимальный набор:

1. Провести серию правильных и намеренно ошибочных тренировок.
2. После каждой законченной сессии пересчитать assessment.
3. Экспортировать `state.snapshot`, `operator.command` и ошибки assessment в JSONL.
4. Собрать хотя бы несколько десятков независимых сессий с обоими классами target.
5. Запустить `generate_dataset.py`.
6. Проверить class balance и отсутствие leakage.
7. Запустить `train_risk_model.py`.
8. Проверить метрики на validation sessions.
9. Положить `.cbm` и `.json` в `ai-service/models`.
10. Перезапустить `ai-service`.
11. Проверить `/v1/predict-risk` и `model_version=risk-catboost-v1`.
12. Подключить периодический вызов `AIGateway.predict_risk()` к активной сессии.
13. В training mode показывать предупреждение, в exam mode только логировать прогноз.

---

# 24. Что считать следующим улучшением после MVP

После успешного бинарного MVP логичное развитие:

```text
NO_ERROR
LATE_ACTION
WRONG_ACTION
WRONG_SEQUENCE
MISSED_ACTION
```

То есть перейти от бинарного `ERROR_IN_NEXT_10_SECONDS` к multiclass prediction.

Но делать это стоит только после накопления достаточного количества примеров каждого класса. Иначе multiclass-модель будет формально работать, но почти всегда выбирать самый частый тип ошибки.

Следующие полезные улучшения:

- автоматический exporter из application backend;
- metrics report после training;
- class weights для дисбаланса;
- подбор threshold по validation data;
- model registry/version manifest;
- inference orchestration во время живой сессии;
- сохранение прогнозов в timeline;
- offline evaluation: prediction → фактическая ошибка;
- drift monitoring при изменении `ktc_backend` и сценариев.

---

# 25. Definition of Done для ML risk prediction

Этап можно считать полноценно работающим, когда одновременно выполняются условия:

- данные собираются backend независимо от React;
- session export воспроизводим;
- dataset строится автоматически;
- отсутствует leakage из будущего;
- train/validation split выполняется по session;
- dataset содержит оба класса;
- обученная CatBoost-модель имеет сохранённые validation metrics;
- `.cbm` и metadata версионированы;
- AI-service успешно загружает модель;
- `/v1/predict-risk` возвращает не fallback, а `risk-catboost-v1`;
- application backend вызывает прогноз во время активной тренировки;
- prediction сохраняется в timeline;
- training mode может показать предупреждение;
- exam mode не раскрывает прогноз оператору;
- после сессии можно сравнить прогнозы с реально обнаруженными assessment-errors;
- существует инструкция, позволяющая повторить полный цикл обучения с нуля.

До выполнения этих пунктов архитектура и pipeline готовы, но ML следует считать экспериментальным контуром, а не валидированной промышленной моделью.
