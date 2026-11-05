"""Score MQTTset packet CSVs and write normalized non-legitimate IDS alerts."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd

from .alerting import write_alert


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="MQTTset CSV to score")
    parser.add_argument("--model", type=Path, default=Path("models/mqtt-random-forest.joblib"))
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
    feature_frame = frame[features].apply(pd.to_numeric, errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
    feature_frame = feature_frame.mask(feature_frame.abs() > 3.0e38)
    predictions = pipeline.predict(feature_frame)
    probabilities = pipeline.predict_proba(feature_frame)
    classes = [str(label) for label in pipeline.named_steps["classifier"].classes_]
    alerts_written = 0
    for index, (prediction, scores) in enumerate(zip(predictions, probabilities)):
        label = str(prediction)
        if label.lower() == "legitimate":
            continue
        confidence = float(max(scores))
        write_alert(
            args.alerts,
            sensor="mqtt-ml",
            rule_id="OT-MQTT-ML-001",
            severity="high" if confidence >= 0.9 else "medium",
            evidence={
                "predicted_label": label,
                "confidence": round(confidence, 6),
                "packet_row": int(index),
                "model_classes": classes,
            },
            event={"protocol": "MQTT", "scenario": "offline-dataset"},
        )
        alerts_written += 1
    print(f"Scored rows: {len(frame)}")
    print(f"Non-legitimate MQTT alerts written: {alerts_written}")
    print(f"Alert file: {args.alerts}")


if __name__ == "__main__":
    main()
