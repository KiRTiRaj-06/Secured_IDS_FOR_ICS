"""Generate controlled telemetry events inside the isolated Compose network."""

from __future__ import annotations

import json
import os
import signal
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

STOP = False


def stop(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def main() -> None:
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    host = os.getenv("MQTT_HOST", "127.0.0.1")
    port = int(os.getenv("MQTT_PORT", "1883"))
    topic = os.getenv("MQTT_TOPIC", "ot/lab/telemetry")
    scenario = os.getenv("SCENARIO", "benign").lower()
    run_id = os.getenv("RUN_ID", f"run-{uuid.uuid4().hex[:8]}")
    interval = max(0.05, float(os.getenv("PUBLISH_INTERVAL", "1.0")))
    max_messages = max(0, int(os.getenv("MAX_MESSAGES", "0")))
    event_path = Path(os.getenv("EVENT_PATH", "output/events.jsonl"))
    if scenario not in {"benign", "fdi", "replay", "flood"}:
        raise SystemExit("SCENARIO must be benign, fdi, replay, or flood")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{run_id}")
    client.connect(host, port, keepalive=30)
    client.loop_start()
    count = 0
    benign_level = 50.0
    replay_payload: dict[str, object] | None = None
    try:
        while not STOP and (max_messages == 0 or count < max_messages):
            count += 1
            level = benign_level + (count % 7) * 0.2
            if scenario == "fdi" and count >= 5:
                level = 125.0
            event: dict[str, object] = {
                "schema_version": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "scenario": scenario,
                "source": "simulated-outstation",
                "point": "tank_level_pct",
                "value": round(level, 2),
                "unit": "%",
                "sequence": count,
            }
            if scenario == "replay":
                if replay_payload is None:
                    replay_payload = event.copy()
                else:
                    event = replay_payload.copy()
                    event["timestamp"] = datetime.now(timezone.utc).isoformat()

            client.publish(topic, json.dumps(event, separators=(",", ":")), qos=1)
            event_path.parent.mkdir(parents=True, exist_ok=True)
            with event_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, separators=(",", ":")) + "\n")
            print(json.dumps({"published": event}, separators=(",", ":")), flush=True)
            time.sleep(interval / 8 if scenario == "flood" else interval)
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
