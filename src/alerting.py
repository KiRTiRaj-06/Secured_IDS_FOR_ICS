"""Shared JSON Lines alert writer used by all project detection components."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def attack_mappings() -> dict[str, dict[str, Any]]:
    path = Path(os.getenv("ATTACK_MAPPING_PATH", "/app/config/attack-mapping.json"))
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    rules = value.get("rules", {}) if isinstance(value, dict) else {}
    return {str(rule_id): rule for rule_id, rule in rules.items() if isinstance(rule, dict)}


def write_alert(
    path: Path,
    *,
    sensor: str,
    rule_id: str,
    severity: str,
    evidence: dict[str, Any],
    event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = event or {}
    alert: dict[str, Any] = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": event.get("run_id"),
        "sensor": sensor,
        "source": event.get("source"),
        "destination": event.get("destination"),
        "protocol": event.get("protocol"),
        "scenario": event.get("scenario"),
        "point": event.get("point"),
        "rule_id": rule_id,
        "severity": severity,
        "evidence": evidence,
    }
    mapping = attack_mappings().get(rule_id)
    if mapping:
        alert["attack_technique"] = mapping
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(alert, separators=(",", ":")) + "\n")
    return alert
