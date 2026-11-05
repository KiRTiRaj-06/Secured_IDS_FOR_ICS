# Architecture and Data Flow

```text
Soft PLC / tank simulator -> MQTT broker -> Python telemetry IDS -> alerts.jsonl -> Wazuh
                                              ^
DNP3 outstation <- DNP3 TCP tap <- DNP3 master/gateway -> MQTT broker
                       |
                       +-> Suricata live NIDS -> normalized alerts.jsonl -> Wazuh

Offline MQTT and DNP3 datasets -> trained Random Forest models -> ML scoring -> alerts.jsonl
Offline PCAP -> Zeek + ICSNPP DNP3 and Suricata -> normalized alerts.jsonl -> Wazuh
```

The project contains two complementary detection paths:

- The Python telemetry IDS evaluates simulated process values and optional trained
  MQTT/DNP3 classification models.
- The passive NIDS inspects live lab traffic without blocking it: Suricata observes
  MQTT at the broker and DNP3 at the TCP tap. Zeek with ICSNPP is retained for
  deeper offline DNP3 PCAP analysis.

All curated alerts share the JSONL schema in `output/alerts.jsonl`. The Wazuh agent
forwards that local artifact to the Wazuh manager for search, dashboards, and
correlation; Wazuh does not make the protocol-parsing or ML classification decision.

The `dnp3_adapter.py` module is the only component permitted to call a DNP3 library.
This keeps the telemetry schema and detection components independent from the
selected DNP3 binding.
