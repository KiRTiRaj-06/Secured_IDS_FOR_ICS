"""Small, explainable telemetry detector; emits JSON Lines for later Wazuh ingestion."""

from __future__ import annotations

import json
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import joblib
import paho.mqtt.client as mqtt

from .alerting import write_alert
from .policy import load_policy

HOST = os.getenv("MQTT_HOST", "127.0.0.1")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("MQTT_TOPIC", "ot/lab/telemetry")
ALERT_PATH = Path(os.getenv("ALERT_PATH", "output/alerts.jsonl"))
recent: dict[str, deque[tuple[int, float]]] = defaultdict(lambda: deque(maxlen=8))
last_sequence: dict[str, int] = {}
rate_window: dict[str, deque[float]] = defaultdict(deque)
rate_alerted: set[str] = set()
last_value: dict[str, float] = {}
last_arrival: dict[str, float] = {}
RATE_LIMIT = int(os.getenv("RATE_LIMIT_MESSAGES", "10"))
RATE_WINDOW_SECONDS = float(os.getenv("RATE_WINDOW_SECONDS", "2.0"))
MODEL_PATH = Path(os.getenv("MODEL_PATH", "/models/random-forest.joblib"))
MODEL_BUNDLE = joblib.load(MODEL_PATH) if MODEL_PATH.is_file() else None
POLICY = load_policy()


def emit_alert(message: dict[str, object], rule_id: str, severity: str, reason: str) -> None:
    alert = write_alert(
        ALERT_PATH,
        sensor="python-ids",
        rule_id=rule_id,
        severity=severity,
        evidence={"reason": reason, "value": message.get("value"), "sequence": message.get("sequence")},
        event=message,
    )
    print(json.dumps({"alert": alert}, separators=(",", ":")), flush=True)


def on_connect(client: mqtt.Client, _userdata: object, _flags: object, reason_code: object, _properties: object) -> None:
    if reason_code == 0:
        client.subscribe(TOPIC, qos=1)
        print(json.dumps({"status": "subscribed", "topic": TOPIC}), flush=True)
    else:
        print(json.dumps({"error": "mqtt_connect_failed", "reason": str(reason_code)}), flush=True)


def on_message(_client: mqtt.Client, _userdata: object, packet: mqtt.MQTTMessage) -> None:
    try:
        message = json.loads(packet.payload)
        if not isinstance(message, dict):
            raise ValueError("payload must be a JSON object")
        point = str(message["point"])
        value = float(message["value"])
        sequence = int(message["sequence"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": "invalid_telemetry", "detail": str(exc)}), flush=True)
        return

    stream = f"{message.get('run_id') or 'default'}:{message.get('source') or 'unknown'}:{point}"
    history = recent[stream]
    prior_seq = last_sequence.get(stream)
    point_policy = POLICY.points.get(point)
    if point_policy is None:
        emit_alert(message, "OT-POLICY-001", "low", "telemetry point is not present in the IDS policy")
        return
    now = monotonic()
    arrivals = rate_window[stream]
    arrivals.append(now)
    while arrivals and now - arrivals[0] > RATE_WINDOW_SECONDS:
        arrivals.popleft()
    if len(arrivals) > POLICY.rate_limit_messages and stream not in rate_alerted:
        emit_alert(message, "OT-FLOOD-001", "medium", f"more than {POLICY.rate_limit_messages} messages in {POLICY.rate_window_seconds:g} seconds")
        rate_alerted.add(stream)
    if len(arrivals) <= POLICY.rate_limit_messages:
        rate_alerted.discard(stream)
    if prior_seq is not None and sequence <= prior_seq:
        emit_alert(message, "OT-REPLAY-001", "medium", "sequence did not increase")
    if not point_policy.minimum <= value <= point_policy.maximum:
        emit_alert(message, "OT-RANGE-001", "high", f"value outside configured {point_policy.minimum:g}-{point_policy.maximum:g} range")
    if history and abs(value - history[-1][1]) > point_policy.max_delta:
        emit_alert(message, "OT-RATE-001", "high", f"change exceeded configured {point_policy.max_delta:g} point delta")
    if MODEL_BUNDLE is not None:
        elapsed = now - last_arrival.get(stream, now)
        features = [[value, value - last_value.get(stream, value), sequence - (prior_seq if prior_seq is not None else sequence - 1), elapsed]]
        model = MODEL_BUNDLE["model"]
        if int(model.predict(features)[0]) == 1:
            emit_alert(message, "OT-ML-001", "medium", "trained model classified telemetry as attack")
    last_sequence[stream] = sequence
    last_value[stream] = value
    last_arrival[stream] = now
    history.append((sequence, value))


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ics-ids-detector")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(HOST, PORT, keepalive=30)
    client.loop_forever()


if __name__ == "__main__":
    main()
