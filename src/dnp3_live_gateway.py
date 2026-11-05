"""Poll the lab DNP3 outstation and publish its analog point to MQTT."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from time import sleep
from uuid import uuid4

import paho.mqtt.client as mqtt
from dnp3_python.dnp3station.master_new import MyMasterNew


DNP3_HOST = os.getenv("DNP3_HOST", "dnp3-outstation")
DNP3_SOURCE = os.getenv("DNP3_SOURCE", "dnp3-outstation")
DNP3_PORT = int(os.getenv("DNP3_PORT", "20000"))
MASTER_ADDRESS = int(os.getenv("DNP3_MASTER_ADDRESS", "2"))
OUTSTATION_ADDRESS = int(os.getenv("DNP3_OUTSTATION_ADDRESS", "1"))
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "ot/lab/telemetry")
POLL_INTERVAL = max(1.0, float(os.getenv("DNP3_POLL_INTERVAL", "3.0")))


def main() -> None:
    dnp3 = MyMasterNew(
        master_ip="0.0.0.0",
        outstation_ip=DNP3_HOST,
        port=DNP3_PORT,
        master_id=MASTER_ADDRESS,
        outstation_id=OUTSTATION_ADDRESS,
    )
    dnp3.start()
    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dnp3-mqtt-gateway")
    publisher.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    publisher.loop_start()
    sequence = 0
    run_id = "dnp3-live-" + uuid4().hex[:8]
    try:
        while True:
            value = dnp3.get_val_by_group_variation_index(30, 6, 0)
            if value is not None:
                sequence += 1
                event = {
                    "schema_version": 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "sensor": "dnp3-gateway",
                    "source": DNP3_SOURCE,
                    "destination": "mosquitto",
                    "protocol": "DNP3-to-MQTT",
                    "scenario": "dnp3-live-lab",
                    "point": "tank_level_pct",
                    "value": float(value),
                    "sequence": sequence,
                }
                publisher.publish(MQTT_TOPIC, json.dumps(event), qos=1)
                print(json.dumps({"published": event}), flush=True)
            else:
                print("DNP3 poll returned no analog value yet", flush=True)
            sleep(POLL_INTERVAL)
    finally:
        publisher.loop_stop()
        publisher.disconnect()
        dnp3.shutdown()


if __name__ == "__main__":
    main()
