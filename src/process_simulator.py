"""Safe Level 0/1 tank process simulator for the private Docker lab.

It is deliberately a software-only model.  It accepts two bounded operator
commands through MQTT and emits telemetry in the same schema as the detector.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from time import sleep
from uuid import uuid4

import paho.mqtt.client as mqtt


HOST = os.getenv("MQTT_HOST", "127.0.0.1")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TELEMETRY_TOPIC = os.getenv("MQTT_TOPIC", "ot/lab/telemetry")
COMMAND_TOPIC = os.getenv("COMMAND_TOPIC", "ot/lab/command")
INTERVAL = float(os.getenv("PUBLISH_INTERVAL", "1.0"))
RUN_ID = os.getenv("RUN_ID", "live-process-" + uuid4().hex[:8])


@dataclass
class PlantState:
    tank_level_pct: float = 55.0
    inlet_open: bool = True
    pump_enabled: bool = False
    sequence: int = 0


state = PlantState()
state_lock = Lock()


def apply_command(payload: bytes) -> dict[str, object]:
    """Apply only explicit boolean HMI commands; reject everything else."""
    try:
        command = json.loads(payload)
        action = str(command["command"])
        value = command["value"]
        if action not in {"set_pump", "set_inlet"} or not isinstance(value, bool):
            raise ValueError("command must set pump or inlet to a boolean value")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return {"accepted": False, "reason": str(exc)}

    with state_lock:
        if action == "set_pump":
            state.pump_enabled = value
        else:
            state.inlet_open = value
        snapshot = asdict(state)
    return {"accepted": True, "command": action, "value": value, "state": snapshot}


def on_connect(client: mqtt.Client, _userdata: object, _flags: object, reason_code: object, _properties: object) -> None:
    if reason_code == 0:
        client.subscribe(COMMAND_TOPIC, qos=1)
        print(json.dumps({"status": "subscribed", "topic": COMMAND_TOPIC}), flush=True)
    else:
        print(json.dumps({"error": "mqtt_connect_failed", "reason": str(reason_code)}), flush=True)


def on_message(_client: mqtt.Client, _userdata: object, packet: mqtt.MQTTMessage) -> None:
    print(json.dumps({"command_result": apply_command(packet.payload)}), flush=True)


def next_telemetry() -> dict[str, object]:
    with state_lock:
        # Inlet adds 0.8% per tick; the pump removes 1.25% per tick.
        delta = (0.8 if state.inlet_open else 0.0) - (1.25 if state.pump_enabled else 0.0)
        state.tank_level_pct = round(min(100.0, max(0.0, state.tank_level_pct + delta)), 2)
        state.sequence += 1
        return {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": RUN_ID,
            "sensor": "soft-plc",
            "source": "process-simulator",
            "destination": None,
            "protocol": "MQTT-live-sim",
            "scenario": "live-lab",
            "point": "tank_level_pct",
            "value": state.tank_level_pct,
            "sequence": state.sequence,
            "process_state": {
                "inlet_open": state.inlet_open,
                "pump_enabled": state.pump_enabled,
            },
        }


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ics-soft-plc")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(HOST, PORT, keepalive=30)
    client.loop_start()
    try:
        while True:
            telemetry = next_telemetry()
            client.publish(TELEMETRY_TOPIC, json.dumps(telemetry), qos=1)
            print(json.dumps({"telemetry": telemetry}), flush=True)
            sleep(INTERVAL)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
