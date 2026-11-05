"""Normalize Suricata EVE alerts and Zeek ICSNPP DNP3 control logs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def alert_from_suricata(event: dict[str, Any]) -> dict[str, Any] | None:
    if event.get("event_type") != "alert":
        return None
    signature = event.get("alert") or {}
    severity = int(signature.get("severity", 3))
    return {
        "schema_version": 1,
        "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "sensor": "suricata",
        "source": event.get("src_ip"),
        "destination": event.get("dest_ip"),
        "protocol": event.get("app_proto") or event.get("proto"),
        "rule_id": f"SURICATA-{signature.get('signature_id', 'unknown')}",
        "severity": "high" if severity == 1 else "medium" if severity == 2 else "low",
        "evidence": {
            "signature": signature.get("signature"),
            "category": signature.get("category"),
            "pcap_count": event.get("pcap_cnt"),
            "flow_id": event.get("flow_id"),
        },
    }


CONTROL_FUNCTIONS = {
    "OPERATE",
    "DIRECT_OPERATE",
    "DIRECT_OPERATE_NO_ACK",
    "COLD_RESTART",
    "WARM_RESTART",
    "STOP_APPLICATION",
    "INITIALIZE_DATA",
    "DISABLE_UNSOLICITED",
}


def alert_from_dnp3_control(event: dict[str, Any], authorized_sources: set[str]) -> dict[str, Any] | None:
    source = str(event.get("source_h") or event.get("id.orig_h") or "")
    destination = event.get("destination_h") or event.get("id.resp_h")
    raw_function = event.get("function_code") or event.get("fc_request") or ""
    function = str(raw_function).upper().replace(" ", "_")
    if not source or not authorized_sources or function not in CONTROL_FUNCTIONS:
        return None
    if source in authorized_sources:
        return None
    return {
        "schema_version": 1,
        "timestamp": event.get("ts", datetime.now(timezone.utc).isoformat()),
        "sensor": "zeek-icsnpp-dnp3",
        "source": source,
        "destination": destination,
        "protocol": "DNP3",
        "scenario": "unauthorized_command",
        "rule_id": "OT-DNP3-UNAUTHORIZED-SOURCE-001",
        "severity": "high",
        "evidence": {
            "function_code": raw_function,
            "block_type": event.get("block_type"),
            "index_number": event.get("index_number"),
            "operation_type": event.get("operation_type"),
            "status_code": event.get("status_code"),
        },
    }


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: expected JSON Zeek logs; run Zeek with JSON logging enabled") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suricata", type=Path)
    parser.add_argument("--dnp3-control", type=Path)
    parser.add_argument("--authorized-sources", default="", help="comma-separated allowed DNP3 control source IPs")
    parser.add_argument("--alerts", type=Path, default=Path("output/alerts.jsonl"))
    args = parser.parse_args()
    authorized = {item.strip() for item in args.authorized_sources.split(",") if item.strip()}
    findings: list[dict[str, Any]] = []
    dnp3_findings: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    if args.suricata:
        for row in read_json_lines(args.suricata):
            alert = alert_from_suricata(row)
            if alert:
                findings.append(alert)
    if args.dnp3_control:
        for row in read_json_lines(args.dnp3_control):
            alert = alert_from_dnp3_control(row, authorized)
            if alert:
                function = str(alert["evidence"]["function_code"])
                key = (str(alert["sensor"]), str(alert["source"]), str(alert["destination"]), function)
                existing = dnp3_findings.get(key)
                if existing is None:
                    alert["evidence"]["occurrence_count"] = 1
                    alert["evidence"]["first_observed"] = alert["timestamp"]
                    alert["evidence"]["last_observed"] = alert["timestamp"]
                    dnp3_findings[key] = alert
                else:
                    evidence = existing["evidence"]
                    evidence["occurrence_count"] = int(evidence["occurrence_count"]) + 1
                    evidence["last_observed"] = alert["timestamp"]

    findings.extend(dnp3_findings.values())

    args.alerts.parent.mkdir(parents=True, exist_ok=True)
    with args.alerts.open("a", encoding="utf-8") as stream:
        for finding in findings:
            stream.write(json.dumps(finding, separators=(",", ":")) + "\n")
    print(f"Normalized {len(findings)} sensor alert(s) into {args.alerts}")


if __name__ == "__main__":
    main()
