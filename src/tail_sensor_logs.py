"""Follow a live Suricata EVE JSON log and append normalized IDS alerts.

The follower starts at the end of an existing log so enabling the live sensor
does not replay historic records into Wazuh. One signature is emitted per flow.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import sleep
from typing import Any

from .ingest_sensor_logs import alert_from_suricata


EVE_PATH = Path(os.getenv("SURICATA_EVE_PATH", "/sensors/eve.json"))
ALERT_PATH = Path(os.getenv("ALERT_PATH", "/var/log/ics-ids/alerts.jsonl"))
POLL_SECONDS = max(0.1, float(os.getenv("SENSOR_POLL_SECONDS", "0.5")))


def append_alert(alert: dict[str, Any]) -> None:
    ALERT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ALERT_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(alert, separators=(",", ":")) + "\n")
    print(json.dumps({"normalized_alert": alert}), flush=True)


def follow() -> None:
    emitted: set[tuple[str, str]] = set()
    position: int | None = None
    while True:
        if not EVE_PATH.is_file():
            sleep(POLL_SECONDS)
            continue
        size = EVE_PATH.stat().st_size
        if position is None:
            position = size
        elif size < position:
            position = 0
            emitted.clear()
        with EVE_PATH.open(encoding="utf-8") as stream:
            stream.seek(position)
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                alert = alert_from_suricata(event)
                if alert is None:
                    continue
                signature = str(alert["rule_id"])
                flow_id = str(alert["evidence"].get("flow_id", "unknown"))
                key = (signature, flow_id)
                if key not in emitted:
                    emitted.add(key)
                    append_alert(alert)
            position = stream.tell()
        sleep(POLL_SECONDS)


def main() -> None:
    print(json.dumps({"status": "following_suricata", "path": str(EVE_PATH)}), flush=True)
    follow()


if __name__ == "__main__":
    main()
