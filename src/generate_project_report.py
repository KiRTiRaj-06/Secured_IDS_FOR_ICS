"""Create a reproducible Markdown and JSON evidence report for the lab."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_alerts(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    alerts: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on line {line_number} of {path}: {error}") from error
        if isinstance(value, dict):
            alerts.append(value)
    return alerts


def load_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def metric_summary(path: Path) -> dict[str, Any]:
    report = load_object(path)
    if report is None:
        return {"available": False, "path": str(path)}
    accuracy = report.get("accuracy", report.get("test_accuracy"))
    classification = report.get("classification_report")
    if accuracy is None and isinstance(classification, dict):
        accuracy = classification.get("accuracy")
    features = report.get("feature_count")
    if features is None and isinstance(report.get("features"), list):
        features = len(report["features"])
    return {"available": True, "path": str(path), "accuracy": accuracy, "feature_count": features, "classes": report.get("classes", report.get("labels", []))}


def text(value: Any) -> str:
    if value is None:
        return "-"
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(text(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def build_markdown(summary: dict[str, Any]) -> str:
    alerts = summary["alerts"]
    model_rows: list[list[Any]] = []
    for name, model in summary["models"].items():
        if model["available"]:
            model_rows.append([name, model["path"], model.get("accuracy", "not available"), model.get("feature_count", "not available"), ", ".join(map(str, model.get("classes", []))) or "not available"])
        else:
            model_rows.append([name, model["path"], "not available", "not available", "not available"])
    recent = [[alert.get("timestamp"), alert.get("sensor"), alert.get("rule_id"), alert.get("severity"), alert.get("scenario")] for alert in alerts["recent"]]
    return "\n".join([
        "# Secure ICS IDS: Project Evidence", "", f"Generated (UTC): {summary['generated_at']}", "",
        "## Alert Summary", "", f"The local alert artifact contains **{alerts['total']}** JSON alert event(s).", "",
        markdown_table(["Rule ID", "Sensor", "Severity", "Count"], alerts["by_rule"]), "",
        "## Model Evidence", "", markdown_table(["Model", "Metric file", "Held-out accuracy", "Feature count", "Classes"], model_rows), "",
        "## Recent Alert Evidence", "", markdown_table(["Timestamp", "Sensor", "Rule ID", "Severity", "Scenario"], recent or [["No local alerts found", "-", "-", "-", "-"]]), "",
        "## Scope", "", "This evidence is generated from local lab artifacts. Model accuracy values, when present, are held-out dataset results and should not be represented as production performance. The lab is isolated and uses simulated process control only.", "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alerts", type=Path, default=Path("output/alerts.jsonl"))
    parser.add_argument("--mqtt-metrics", type=Path, default=Path("reports/mqtt-model-metrics.json"))
    parser.add_argument("--dnp3-metrics", type=Path, default=Path("reports/dnp3-model-metrics.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/project-evidence.md"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/project-evidence.json"))
    args = parser.parse_args()
    alerts = load_alerts(args.alerts)
    counts = Counter((str(alert.get("rule_id", "unknown")), str(alert.get("sensor", "unknown")), str(alert.get("severity", "unknown"))) for alert in alerts)
    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "alerts": {"source": str(args.alerts), "total": len(alerts), "by_rule": [[rule_id, sensor, severity, count] for (rule_id, sensor, severity), count in sorted(counts.items())], "by_sensor": dict(sorted(Counter(str(alert.get("sensor", "unknown")) for alert in alerts).items())), "by_severity": dict(sorted(Counter(str(alert.get("severity", "unknown")) for alert in alerts).items())), "recent": list(reversed(alerts[-10:]))},
        "models": {"MQTT classifier": metric_summary(args.mqtt_metrics), "DNP3 classifier": metric_summary(args.dnp3_metrics)},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_markdown(summary), encoding="utf-8")
    args.json_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} and {args.json_output}")


if __name__ == "__main__":
    main()
