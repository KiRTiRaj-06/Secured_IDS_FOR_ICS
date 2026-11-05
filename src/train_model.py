"""Build a run-grouped baseline from simulator JSONL event files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit


def load_events(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError(f"{path}:{line_number}: expected a JSON object")
                rows.append(event)

    if not rows:
        raise ValueError("No events found. Run at least one bounded simulator scenario first.")

    frame = pd.DataFrame(rows)
    required = {"run_id", "scenario", "point", "value", "sequence", "timestamp"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing event fields: {', '.join(sorted(missing))}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame["sequence"] = pd.to_numeric(frame["sequence"], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "value", "sequence"]).sort_values(["run_id", "point", "timestamp"])
    grouped = frame.groupby(["run_id", "point"], sort=False)
    frame["value_delta"] = grouped["value"].diff().fillna(0.0)
    frame["sequence_delta"] = grouped["sequence"].diff().fillna(1.0)
    frame["interarrival_seconds"] = grouped["timestamp"].diff().dt.total_seconds().fillna(0.0)
    frame["label"] = (frame["scenario"].astype(str) != "benign").astype("int8")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="event JSONL file(s), e.g. output/events.jsonl")
    parser.add_argument("--model", type=Path, default=Path("models/random-forest.joblib"))
    parser.add_argument("--metrics", type=Path, default=Path("reports/model-metrics.json"))
    args = parser.parse_args()

    frame = load_events(args.inputs)
    if frame["label"].nunique() < 2:
        raise SystemExit("Need both benign and attack-labeled events before training.")
    if frame.groupby("run_id")["label"].nunique().gt(1).any():
        raise SystemExit("Each run_id must contain exactly one scenario to prevent run-level leakage.")

    features = ["value", "value_delta", "sequence_delta", "interarrival_seconds"]
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(splitter.split(frame[features], frame["label"], groups=frame["run_id"]))
    train, test = frame.iloc[train_idx], frame.iloc[test_idx]
    if train["label"].nunique() < 2 or test["label"].nunique() < 2:
        raise SystemExit("The run-level split needs multiple benign and attack runs; collect more independent runs.")

    model = RandomForestClassifier(
        n_estimators=250,
        class_weight="balanced",
        random_state=42,
        min_samples_leaf=2,
        n_jobs=-1,
    )
    model.fit(train[features], train["label"])
    predictions = model.predict(test[features])
    print("Test run IDs:", ", ".join(sorted(test["run_id"].astype(str).unique())))
    print("Confusion matrix [benign, attack]:")
    print(confusion_matrix(test["label"], predictions, labels=[0, 1]))
    report = classification_report(
        test["label"], predictions, labels=[0, 1], target_names=["benign", "attack"], zero_division=0, output_dict=True
    )
    print(json.dumps(report, indent=2))

    args.model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": features, "classes": {0: "benign", 1: "attack"}}, args.model)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    metrics = {
        "report": report,
        "confusion_matrix_labels_benign_attack": confusion_matrix(test["label"], predictions, labels=[0, 1]).tolist(),
        "train_run_ids": sorted(train["run_id"].astype(str).unique()),
        "test_run_ids": sorted(test["run_id"].astype(str).unique()),
        "feature_names": features,
    }
    args.metrics.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"Saved model: {args.model}")
    print(f"Saved metrics: {args.metrics}")


if __name__ == "__main__":
    main()
