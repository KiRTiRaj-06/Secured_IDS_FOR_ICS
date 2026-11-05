"""Score DNP3 Custom_DNP3_Parser flow CSVs and write normalized IDS alerts."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd

from .alerting import write_alert


def value_at(row: pd.Series, name: str) -> object | None:
    for column in row.index:
        if str(column).strip().lower() == name:
            value = row[column]
            return None if pd.isna(value) else value
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="DNP3 Custom_DNP3_Parser CSV to score")
    parser.add_argument("--model", type=Path, default=Path("models/dnp3-random-forest.joblib"))
    parser.add_argument("--alerts", type=Path, default=Path("output/alerts.jsonl"))
    parser.add_argument("--limit", type=int, default=0, help="Optional maximum number of rows to score")
    args = parser.parse_args()

    bundle = joblib.load(args.model)
    pipeline = bundle["pipeline"]
    features: list[str] = bundle["features"]
    frame = pd.read_csv(args.input, low_memory=False)
    if args.limit:
        frame = frame.head(args.limit)
    missing = [feature for feature in features if feature not in frame.columns]
    if missing:
        raise ValueError(f"Input is missing {len(missing)} model features, starting with: {', '.join(missing[:5])}")
    feature_frame = frame[features].apply(pd.to_numeric, errors="coerce")
    predictions = pipeline.predict(feature_frame)
    probabilities = pipeline.predict_proba(feature_frame)
    classes = [str(label) for label in pipeline.named_steps["classifier"].classes_]
    alerts_written = 0
    for index, (prediction, scores) in enumerate(zip(predictions, probabilities)):
        label = str(prediction)
        if label == "NORMAL":
            continue
        row = frame.iloc[index]
        confidence = float(max(scores))
        write_alert(
            args.alerts,
            sensor="dnp3-ml",
            rule_id="OT-DNP3-ML-001",
            severity="high" if confidence >= 0.9 else "medium",
            evidence={
                "predicted_label": label,
                "confidence": round(confidence, 6),
                "flow_row": int(index),
                "model_classes": classes,
            },
            event={
                "source": value_at(row, "source ip"),
                "destination": value_at(row, "destination ip"),
                "protocol": "DNP3",
                "scenario": "offline-dataset",
                "point": None,
            },
        )
        alerts_written += 1
    print(f"Scored rows: {len(frame)}")
    print(f"Non-normal DNP3 alerts written: {alerts_written}")
    print(f"Alert file: {args.alerts}")


if __name__ == "__main__":
    main()
