# Risk model dataset

The risk model is trained on telemetry captured by the application backend from the digital twin. The repository does not invent process physics and does not commit generated CSV datasets or binary CatBoost models.

`generate_dataset.py` expects JSONL with one session export per line:

```json
{
  "session_id": "uuid",
  "scenario_code": "oil-heating-basic-startup",
  "operator_profile": {"previous_errors": {"LATE_ACTION": 2}},
  "snapshots": [{"simulation_time_ms": 10000, "revision": 10, "sensors": {}, "pumps": {}, "regulators": {}, "alarms": []}],
  "actions": [{"simulation_time_ms": 8000, "equipment_id": "H1A", "action": "start", "payload": {}}],
  "errors": [{"occurred_at_ms": 17000, "error_code": "LATE_ACTION"}]
}
```

For each snapshot at time `t`, features are built only from telemetry and actions with timestamps `<= t`. The binary target is `1` when an assessed error occurs in `(t, t + 10s]`. This prevents target leakage from future state/actions into the feature vector.

Example:

```bash
python scripts/generate_dataset.py datasets/session_exports.jsonl datasets/risk.csv
python scripts/train_risk_model.py datasets/risk.csv
```

Training splits by `session_id`, not by individual rows, so windows from the same training session do not appear in both train and validation partitions.
