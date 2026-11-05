"""Train and evaluate an MQTT packet classifier from MQTTset CSV splits."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import Pipeline


PAYLOAD_COLUMNS = {"mqtt.msg", "mqtt.willmsg"}


def label_column(frame: pd.DataFrame) -> str:
    for column in frame.columns:
        if str(column).strip().lower() == "target":
            return column
    raise ValueError("Expected a target column in the MQTT CSV.")


def numeric_features(train: pd.DataFrame, test: pd.DataFrame, target: str) -> tuple[list[str], pd.DataFrame, pd.DataFrame]:
    features: list[str] = []
    for column in train.columns:
        normalized = str(column).strip().lower()
        if column == target or normalized.startswith("unnamed:") or normalized in PAYLOAD_COLUMNS or column not in test.columns:
            continue
        train_values = pd.to_numeric(train[column], errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
        test_values = pd.to_numeric(test[column], errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
        # scikit-learn's tree implementation converts inputs to float32.
        train_values = train_values.mask(train_values.abs() > 3.0e38)
        test_values = test_values.mask(test_values.abs() > 3.0e38)
        if train_values.notna().any() and train_values.nunique(dropna=True) > 1:
            train[column] = train_values
            test[column] = test_values
            features.append(column)
    if not features:
        raise ValueError("No usable numeric MQTT features were found.")
    return features, train, test


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path, help="MQTTset training CSV")
    parser.add_argument("--test", required=True, type=Path, help="MQTTset testing CSV")
    parser.add_argument("--model", type=Path, default=Path("models/mqtt-random-forest.joblib"))
    parser.add_argument("--metrics", type=Path, default=Path("reports/mqtt-model-metrics.json"))
    args = parser.parse_args()

    train = pd.read_csv(args.train, low_memory=False)
    test = pd.read_csv(args.test, low_memory=False)
    target = label_column(train)
    if target not in test.columns:
        raise ValueError("Training and testing CSV files use different target columns.")
    train[target] = train[target].astype(str).str.strip()
    test[target] = test[target].astype(str).str.strip()
    features, train, test = numeric_features(train, test, target)
    labels = sorted(set(train[target]) | set(test[target]))
    if len(labels) < 2:
        raise ValueError("Need at least two MQTT target classes to train a classifier.")

    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    class_weight="balanced",
                    min_samples_leaf=2,
                    n_jobs=-1,
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(train[features], train[target])
    predictions = model.predict(test[features])
    classifier = model.named_steps["classifier"]
    importance = sorted(
        ({"feature": feature, "importance": float(score)} for feature, score in zip(features, classifier.feature_importances_)),
        key=lambda item: item["importance"],
        reverse=True,
    )
    report = classification_report(test[target], predictions, labels=labels, output_dict=True, zero_division=0)
    metrics = {
        "dataset": "MQTTset / FINAL_CSV reduced split",
        "algorithm": "RandomForestClassifier",
        "algorithm_parameters": classifier.get_params(),
        "train_csv": str(args.train),
        "test_csv": str(args.test),
        "label_column": str(target),
        "classes": labels,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_class_counts": dict(sorted(Counter(train[target]).items())),
        "test_class_counts": dict(sorted(Counter(test[target]).items())),
        "feature_count": len(features),
        "feature_names": features,
        "top_feature_importance": importance[:20],
        "accuracy": float(accuracy_score(test[target], predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(test[target], predictions)),
        "confusion_matrix_labels": labels,
        "confusion_matrix": confusion_matrix(test[target], predictions, labels=labels).tolist(),
        "classification_report": report,
        "limitations": [
            "This evaluates MQTTset's supplied split, not live ICS traffic.",
            "The model consumes extracted packet fields, not raw MQTT protocol sessions.",
            "Non-numeric payload fields are excluded from this baseline.",
        ],
    }
    args.model.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": model, "features": features, "classes": labels, "metadata": metrics}, args.model)
    args.metrics.write_text(json.dumps(metrics, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({key: metrics[key] for key in ("train_rows", "test_rows", "classes", "feature_count", "accuracy", "balanced_accuracy")}, indent=2))
    print(f"Saved model: {args.model}")
    print(f"Saved metrics: {args.metrics}")


if __name__ == "__main__":
    main()
