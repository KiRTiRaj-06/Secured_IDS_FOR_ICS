"""Poll a DNP3 source and publish normalized point values to MQTT."""

from __future__ import annotations

import json
import os
import signal
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

from .dnp3_adapter import create_client

STOP = False
POINT_MAP = {0: ("tank_level_pct", "%")}


def stop(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def main() -> None:
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    mqtt_host = os.getenv("MQTT_HOST", "mosquitto")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    topic = os.getenv("MQTT_TOPIC", "ot/lab/telemetry")
    poll_interval = max(0.1, float(os.getenv("DNP3_POLL_INTERVAL", "2.0")))
    run_id = os.getenv("RUN_ID", f"gateway-{uuid.uuid4().hex[:8]}")
    event_path = Path(os.getenv("EVENT_PATH", "output/events.jsonl"))
    client = create_client()
    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dnp3-mqtt-gateway")
    publisher.connect(mqtt_host, mqtt_port, keepalive=30)
    publisher.loop_start()
    sequence = 0
    try:
        while not STOP:
            for point_index, value in client.read_analog_points().items():
                point_name, unit = POINT_MAP.get(point_index, (f"analog_{point_index}", "unknown"))
                sequence += 1
                event = {
                    "schema_version": 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "scenario": "benign",
                    "source": "dnp3-gateway",
                    "protocol": "DNP3-to-MQTT",
                    "point": point_name,
                    "value": value,
                    "unit": unit,
                    "sequence": sequence,
                }
                publisher.publish(topic, json.dumps(event, separators=(",", ":")), qos=1)
                event_path.parent.mkdir(parents=True, exist_ok=True)
                with event_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, separators=(",", ":")) + "\n")
            time.sleep(poll_interval)
    finally:
        publisher.disconnect()
        publisher.loop_stop()


if __name__ == "__main__":
    main()
