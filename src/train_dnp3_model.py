"""Train and evaluate a DNP3 classifier from supplied Custom_DNP3_Parser CSV splits."""

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


IDENTIFIER_COLUMNS = {
    "unnamed: 0",
    "flow id",
    "source ip",
    "destination ip",
    "source port",
    "destination port",
    "protocol",
    "date",
    "framesrc",
    "framedst",
    "firstpacketdir",
}


def find_label_column(frame: pd.DataFrame) -> str:
    for column in frame.columns:
        if str(column).strip().lower() == "label":
            return column
    raise ValueError("Expected a Label column in the DNP3 CSV.")


def select_numeric_features(train: pd.DataFrame, test: pd.DataFrame, label_column: str) -> tuple[list[str], pd.DataFrame, pd.DataFrame]:
    features: list[str] = []
    normalized = {column: str(column).strip().lower() for column in train.columns}
    for column in train.columns:
        if (
            column == label_column
            or normalized[column] in IDENTIFIER_COLUMNS
            or normalized[column].startswith("unnamed:")
            or column not in test.columns
        ):
            continue
        train_values = pd.to_numeric(train[column], errors="coerce")
        test_values = pd.to_numeric(test[column], errors="coerce")
        if train_values.notna().any() and train_values.nunique(dropna=True) > 1:
            train[column] = train_values
            test[column] = test_values
            features.append(column)
    if not features:
        raise ValueError("No usable numeric features were found after excluding identifiers.")
    return features, train, test


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path, help="Custom_DNP3_Parser training CSV")
    parser.add_argument("--test", required=True, type=Path, help="Custom_DNP3_Parser testing CSV")
    parser.add_argument("--model", type=Path, default=Path("models/dnp3-random-forest.joblib"))
    parser.add_argument("--metrics", type=Path, default=Path("reports/dnp3-model-metrics.json"))
    args = parser.parse_args()

    train = pd.read_csv(args.train, low_memory=False)
    test = pd.read_csv(args.test, low_memory=False)
    label_column = find_label_column(train)
    if label_column not in test.columns:
        raise ValueError("Training and testing CSV files use different Label columns.")

    train[label_column] = train[label_column].astype(str).str.strip()
    test[label_column] = test[label_column].astype(str).str.strip()
    features, train, test = select_numeric_features(train, test, label_column)
    labels = sorted(set(train[label_column]) | set(test[label_column]))
    if len(labels) < 2:
        raise ValueError("Need at least two classes to train a classifier.")

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
    model.fit(train[features], train[label_column])
    predictions = model.predict(test[features])
    classifier = model.named_steps["classifier"]
    importance = sorted(
        ({"feature": feature, "importance": float(score)} for feature, score in zip(features, classifier.feature_importances_)),
        key=lambda item: item["importance"],
        reverse=True,
    )
    report = classification_report(test[label_column], predictions, labels=labels, output_dict=True, zero_division=0)
    metrics = {
        "dataset": "DNP3_Intrusion_Detection_Dataset_Final / Custom_DNP3_Parser",
        "algorithm": "RandomForestClassifier",
        "algorithm_parameters": classifier.get_params(),
        "train_csv": str(args.train),
        "test_csv": str(args.test),
        "label_column": str(label_column),
        "classes": labels,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_class_counts": dict(sorted(Counter(train[label_column]).items())),
        "test_class_counts": dict(sorted(Counter(test[label_column]).items())),
        "feature_count": len(features),
        "feature_names": features,
        "top_feature_importance": importance[:20],
        "accuracy": float(accuracy_score(test[label_column], predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(test[label_column], predictions)),
        "confusion_matrix_labels": labels,
        "confusion_matrix": confusion_matrix(test[label_column], predictions, labels=labels).tolist(),
        "classification_report": report,
        "limitations": [
            "This evaluates the dataset's supplied split, not live production traffic.",
            "The model consumes flow summaries, not individual packets.",
            "IP addresses, ports, flow IDs, timestamps, and direction identifiers are excluded to reduce dataset-specific leakage.",
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
