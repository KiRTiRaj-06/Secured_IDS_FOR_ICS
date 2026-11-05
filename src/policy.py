"""Loads the process and detection policy from a versioned JSON file."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PointPolicy:
    minimum: float
    maximum: float
    max_delta: float


@dataclass(frozen=True)
class DetectionPolicy:
    points: dict[str, PointPolicy]
    rate_limit_messages: int
    rate_window_seconds: float


def load_policy() -> DetectionPolicy:
    policy_path = Path(os.getenv("IDS_POLICY_PATH", "/app/config/ids-policy.json"))
    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    points = {
        name: PointPolicy(
            minimum=float(value["minimum"]),
            maximum=float(value["maximum"]),
            max_delta=float(value["max_delta"]),
        )
        for name, value in raw["telemetry_points"].items()
    }
    return DetectionPolicy(
        points=points,
        rate_limit_messages=int(os.getenv("RATE_LIMIT_MESSAGES", raw["rate_limit_messages"])),
        rate_window_seconds=float(os.getenv("RATE_WINDOW_SECONDS", raw["rate_window_seconds"])),
    )
