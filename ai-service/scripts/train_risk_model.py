from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from catboost import CatBoostClassifier

from app.features.risk import FEATURE_NAMES

MODEL_VERSION = "risk-catboost-v2"
TARGET = "target_error_next_10s"


def load_dataset(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def split_by_session(
    rows: list[dict[str, str]], seed: int = 21, validation_ratio: float = 0.2
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["session_id"]].append(row)
    session_ids = sorted(grouped)
    random.Random(seed).shuffle(session_ids)
    validation_count = max(1, round(len(session_ids) * validation_ratio)) if len(session_ids) > 1 else 0
    validation_ids = set(session_ids[:validation_count])
    train = [row for session_id in session_ids if session_id not in validation_ids for row in grouped[session_id]]
    validation = [row for session_id in session_ids if session_id in validation_ids for row in grouped[session_id]]
    return train, validation


def matrix(rows: list[dict[str, str]]) -> tuple[list[list[float]], list[int]]:
    x = [[float(row[name]) for name in FEATURE_NAMES] for row in rows]
    y = [int(row[TARGET]) for row in rows]
    return x, y


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the binary ERROR_IN_NEXT_10_SECONDS model")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--model", type=Path, default=Path("models/risk-catboost-v2.cbm"))
    parser.add_argument("--metadata", type=Path, default=Path("models/risk-catboost-v2.json"))
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    rows = load_dataset(args.dataset)
    if len(rows) < 20:
        raise SystemExit("Need at least 20 dataset rows")
    if len({row[TARGET] for row in rows}) < 2:
        raise SystemExit("Dataset must contain both positive and negative targets")

    train_rows, validation_rows = split_by_session(rows)
    x_train, y_train = matrix(train_rows)
    x_validation, y_validation = matrix(validation_rows)

    model = CatBoostClassifier(
        iterations=args.iterations,
        depth=6,
        learning_rate=0.05,
        loss_function="Logloss",
        eval_metric="AUC",
        random_seed=21,
        verbose=False,
        allow_writing_files=False,
    )
    fit_kwargs = {}
    if validation_rows and len(set(y_validation)) > 1:
        fit_kwargs["eval_set"] = (x_validation, y_validation)
        fit_kwargs["early_stopping_rounds"] = 50
    model.fit(x_train, y_train, **fit_kwargs)

    args.model.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(args.model))
    importances = model.get_feature_importance()
    metadata = {
        "model_version": MODEL_VERSION,
        "target": "ERROR_IN_NEXT_10_SECONDS",
        "horizon_seconds": 10,
        "threshold": args.threshold,
        "feature_names": FEATURE_NAMES,
        "feature_importances": {
            name: float(value) for name, value in zip(FEATURE_NAMES, importances, strict=True)
        },
        "training_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "seed": 21,
        "data_provenance": "digital-twin session exports transformed by generate_dataset.py",
    }
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {MODEL_VERSION} to {args.model}")


if __name__ == "__main__":
    main()
