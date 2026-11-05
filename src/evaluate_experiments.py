"""Evaluate manifest-backed lab runs without overstating unavailable metrics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on line {line_number} of {path}: {error}") from error
        if isinstance(value, dict):
            rows.append(value)
    return rows


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def scenario_rules(directory: Path, scenario: str) -> list[str]:
    path = directory / f"{scenario}.json"
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    rules = value.get("expected_rules", []) if isinstance(value, dict) else []
    return [str(rule) for rule in rules if isinstance(rule, str)]


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifests", type=Path, default=Path("data/manifests"))
    parser.add_argument("--scenarios", type=Path, default=Path("scenarios"))
    parser.add_argument("--events", type=Path, default=Path("output/events.jsonl"))
    parser.add_argument("--alerts", type=Path, default=Path("output/alerts.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/experiment-evaluation.md"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/experiment-evaluation.json"))
    args = parser.parse_args()

    manifests = []
    for path in sorted(args.manifests.glob("*.json")) if args.manifests.is_dir() else []:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and isinstance(value.get("run_id"), str) and isinstance(value.get("scenario"), str):
            manifests.append(value)
    if not manifests:
        raise SystemExit(f"No usable manifests found in {args.manifests}")

    events = read_json_lines(args.events)
    alerts = read_json_lines(args.alerts)
    results: list[dict[str, Any]] = []
    expected_total = 0
    expected_matched = 0
    benign_alerts = 0
    benign_runs = 0

    for manifest in manifests:
        run_id = manifest["run_id"]
        scenario = manifest["scenario"]
        expected = scenario_rules(args.scenarios, scenario)
        run_events = [event for event in events if event.get("run_id") == run_id]
        run_alerts = [alert for alert in alerts if alert.get("run_id") == run_id]
        observed = sorted({str(alert.get("rule_id")) for alert in run_alerts if alert.get("rule_id")})
        matched = sorted(set(expected) & set(observed))
        event_times = [parsed for event in run_events if (parsed := parse_time(event.get("timestamp"))) is not None]
        alert_times = [parsed for alert in run_alerts if (parsed := parse_time(alert.get("timestamp"))) is not None]
        delay = None
        if event_times and alert_times:
            delay = round((min(alert_times) - min(event_times)).total_seconds(), 3)
        if scenario == "benign":
            benign_runs += 1
            benign_alerts += len(run_alerts)
        expected_total += len(expected)
        expected_matched += len(matched)
        results.append({
            "run_id": run_id,
            "scenario": scenario,
            "events": len(run_events),
            "alerts": len(run_alerts),
            "expected_rules": expected,
            "observed_rules": observed,
            "matched_rules": matched,
            "rule_coverage": round(len(matched) / len(expected), 3) if expected else None,
            "detection_delay_seconds": delay,
        })

    summary = {
        "manifest_count": len(results),
        "events_source": str(args.events),
        "alerts_source": str(args.alerts),
        "expected_rule_coverage": round(expected_matched / expected_total, 3) if expected_total else None,
        "benign_alerts_per_run": round(benign_alerts / benign_runs, 3) if benign_runs else None,
        "notes": [
            "Rule coverage measures whether each scenario's expected rule appeared for that run.",
            "Detection delay is measured from the first recorded event to the first alert carrying the same run_id.",
            "Precision, recall, and F1 require per-event ground truth and are reported by the dataset model metric files, not inferred from this manifest summary.",
            "Network sensor alerts without a run_id are intentionally excluded from per-run calculations to avoid incorrect attribution.",
        ],
        "runs": results,
    }
    rows = [[run["run_id"], run["scenario"], run["events"], run["alerts"], ", ".join(run["matched_rules"]) or "-", run["rule_coverage"] if run["rule_coverage"] is not None else "n/a", run["detection_delay_seconds"] if run["detection_delay_seconds"] is not None else "n/a"] for run in results]
    markdown = "\n".join([
        "# Experiment Evaluation", "",
        markdown_table(["Run ID", "Scenario", "Events", "Alerts", "Matched rules", "Rule coverage", "Detection delay (s)"], rows), "",
        "## Aggregate", "",
        f"- Expected-rule coverage: {summary['expected_rule_coverage'] if summary['expected_rule_coverage'] is not None else 'n/a'}",
        f"- Benign alerts per run: {summary['benign_alerts_per_run'] if summary['benign_alerts_per_run'] is not None else 'n/a'}", "",
        "## Measurement Notes", "", *[f"- {note}" for note in summary["notes"]], "",
    ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    args.json_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} and {args.json_output}")


if __name__ == "__main__":
    main()
