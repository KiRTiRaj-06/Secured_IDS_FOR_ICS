"""Summarize which expected scenario rules appeared in a run's JSONL alerts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--alerts", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/scenario-evaluation.json"))
    args = parser.parse_args()
    scenario = load_json(args.scenario)
    expected = set(scenario.get("expected_rules", []))
    counts: Counter[str] = Counter()
    with args.alerts.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                alert = json.loads(line)
                if isinstance(alert, dict) and isinstance(alert.get("rule_id"), str):
                    counts[alert["rule_id"]] += 1
    observed = set(counts)
    result = {
        "scenario": scenario.get("id"),
        "expected_rules": sorted(expected),
        "observed_rule_counts": dict(sorted(counts.items())),
        "matched_expected_rules": sorted(expected & observed),
        "missing_expected_rules": sorted(expected - observed),
        "unexpected_rules": sorted(observed - expected),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
