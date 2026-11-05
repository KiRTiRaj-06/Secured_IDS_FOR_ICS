"""Minimal localhost HMI for the simulated tank process.

The HMI never connects to real control equipment.  It publishes narrowly
validated commands to the private lab MQTT broker and renders live telemetry.
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any

import paho.mqtt.client as mqtt


HOST = os.getenv("MQTT_HOST", "127.0.0.1")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TELEMETRY_TOPIC = os.getenv("MQTT_TOPIC", "ot/lab/telemetry")
COMMAND_TOPIC = os.getenv("COMMAND_TOPIC", "ot/lab/command")
HTTP_HOST = os.getenv("HMI_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("HMI_PORT", "8080"))
ALERT_PATH = os.getenv("ALERT_PATH", "/var/log/ics-ids/alerts.jsonl")
latest: dict[str, Any] = {"connected": False, "message": "Waiting for process telemetry"}
telemetry_by_source: dict[str, dict[str, Any]] = {}
latest_lock = Lock()
mqtt_client: mqtt.Client | None = None


def on_connect(client: mqtt.Client, _userdata: object, _flags: object, reason_code: object, _properties: object) -> None:
    if reason_code == 0:
        client.subscribe(TELEMETRY_TOPIC, qos=1)
        with latest_lock:
            latest["connected"] = True


def on_message(_client: mqtt.Client, _userdata: object, packet: mqtt.MQTTMessage) -> None:
    try:
        message = json.loads(packet.payload)
        if isinstance(message, dict):
            with latest_lock:
                latest.clear()
                latest.update(message)
                latest["connected"] = True
                source = str(message.get("source") or message.get("sensor") or "unknown")
                telemetry_by_source[source] = {**message, "connected": True}
    except json.JSONDecodeError:
        pass


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ICS Lab HMI</title><style>
:root{font-family:Arial,sans-serif;color:#16222a;background:#eef3f4}body{margin:0}.bar{background:#163b4a;color:#fff;padding:16px 24px;font-weight:700}.layout{max-width:920px;margin:28px auto;padding:0 20px;display:grid;gap:20px;grid-template-columns:1.1fr .9fr}.panel{background:#fff;border:1px solid #bfd0d5;padding:22px;border-radius:6px}.tank{height:280px;border:6px solid #245468;position:relative;background:#e8f0f1;overflow:hidden}.water{position:absolute;bottom:0;width:100%;background:#2d9c9c;transition:height .35s}.level{font-size:46px;font-weight:700;margin:12px 0}.status{color:#38624d;font-weight:700}.control{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;border-top:1px solid #d6e0e2;padding:14px 0}.control:first-of-type{border-top:0}.switch{padding:9px 14px;border:1px solid #245468;border-radius:4px;background:#fff;color:#163b4a;font-weight:700;cursor:pointer}.switch.active{background:#245468;color:#fff}.meta{color:#53666d;font-size:14px}@media(max-width:650px){.layout{grid-template-columns:1fr}.tank{height:220px}}</style></head>
<body><div class="bar">ICS Lab HMI - Simulated Tank Process</div><main class="layout"><section class="panel"><div class="meta" id="connection">Connecting to simulator</div><div class="level" id="level">--%</div><div class="tank"><div class="water" id="water"></div></div><p class="meta" id="details">No telemetry received yet.</p></section><section class="panel"><h2>Operator Controls</h2><p class="meta">Commands apply only to the Docker lab process simulator.</p><div class="control"><span>Inlet valve</span><button class="switch" id="inlet" onclick="toggle('set_inlet','inlet')">Loading</button></div><div class="control"><span>Transfer pump</span><button class="switch" id="pump" onclick="toggle('set_pump','pump')">Loading</button></div><p class="status" id="result"></p></section></main><script>
let process={};async function refresh(){try{const r=await fetch('/api/state');process=await r.json();const p=process.process_state||{};const level=Number(process.value);document.getElementById('connection').textContent=process.connected?'Live MQTT telemetry':'Waiting for process telemetry';document.getElementById('level').textContent=Number.isFinite(level)?level.toFixed(1)+'%':'--%';document.getElementById('water').style.height=(Number.isFinite(level)?level:0)+'%';document.getElementById('details').textContent='Sequence: '+(process.sequence??'--')+' | Updated: '+(process.timestamp??'--');button('inlet',!!p.inlet_open);button('pump',!!p.pump_enabled)}catch(e){document.getElementById('connection').textContent='HMI connection unavailable'}}function button(id,on){const b=document.getElementById(id);b.textContent=on?'ON':'OFF';b.classList.toggle('active',on)}async function toggle(command,id){const key=id==='inlet'?'inlet_open':'pump_enabled';const value=!(process.process_state||{})[key];const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command,value})});const answer=await r.json();document.getElementById('result').textContent=answer.accepted?'Command sent to soft PLC.':answer.reason}refresh();setInterval(refresh,1000);</script></body></html>"""

DEMO_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ICS IDS Console</title><style>:root{font-family:Arial,sans-serif;color:#172a31;background:#edf2f3}*{box-sizing:border-box}body{margin:0}.bar{background:#163b4a;color:#fff;padding:15px 24px;display:flex;justify-content:space-between;align-items:center}.bar a{color:#fff;text-decoration:none;border:1px solid #81b7bc;padding:7px 10px;border-radius:4px}.wrap{max-width:1180px;margin:24px auto;padding:0 18px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.panel{background:#fff;border:1px solid #c5d5d9;border-radius:6px;padding:18px}.kicker{color:#567078;font-size:12px;font-weight:700;text-transform:uppercase}.value{font-size:30px;font-weight:700;margin-top:7px}.muted{color:#60757c;font-size:13px}.wide{margin-top:14px}.path{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;align-items:center;text-align:center}.node{border:1px solid #b8cbd0;padding:12px 6px;border-radius:5px;background:#f8fbfb;font-size:13px;font-weight:700}.arrow{color:#2d8384;font-size:22px}.alerts{display:grid;gap:8px;max-height:360px;overflow:auto}.alert{border-left:5px solid #d4a332;background:#f8faf9;padding:10px 12px}.alert.high{border-left-color:#c24848}.alert.medium{border-left-color:#d08a32}.rule{font-weight:700}.scenario{display:grid;grid-template-columns:28px 1fr;gap:9px;padding:11px 0;border-top:1px solid #deeaec}.scenario:first-child{border-top:0}.step{height:24px;width:24px;border-radius:50%;background:#245468;color:#fff;text-align:center;line-height:24px;font-size:12px;font-weight:700}@media(max-width:760px){.grid{grid-template-columns:1fr}.path{grid-template-columns:1fr}.arrow{transform:rotate(90deg)}}</style></head><body><header class="bar"><strong>ICS IDS Demonstration Console</strong><a href="/">Open HMI</a></header><main class="wrap"><section class="grid"><article class="panel"><div class="kicker">Soft PLC tank</div><div class="value" id="process">Waiting</div><div class="muted" id="processMeta">No process telemetry</div></article><article class="panel"><div class="kicker">DNP3 analog input 0</div><div class="value" id="dnp3">Waiting</div><div class="muted" id="dnp3Meta">No DNP3 gateway telemetry</div></article><article class="panel"><div class="kicker">Recent IDS events</div><div class="value" id="count">0</div><div class="muted" id="countMeta">No alerts in the local feed</div></article></section><section class="panel wide"><div class="kicker">Live laboratory path</div><div class="path"><div class="node">Soft PLC / HMI</div><div class="arrow">&#8594;</div><div class="node">MQTT + Python IDS</div><div class="arrow">&#8594;</div><div class="node">Wazuh</div></div><div class="path" style="margin-top:10px"><div class="node">DNP3 Master</div><div class="arrow">&#8594;</div><div class="node">DNP3 Tap + Suricata</div><div class="arrow">&#8594;</div><div class="node">DNP3 Outstation</div></div></section><section class="grid wide"><article class="panel"><div class="kicker">Demonstration sequence</div><div class="scenario"><span class="step">1</span><span>Show normal tank behavior in the HMI.</span></div><div class="scenario"><span class="step">2</span><span>Show MQTT command observation in Wazuh.</span></div><div class="scenario"><span class="step">3</span><span>Show live DNP3 traffic through the tap.</span></div><div class="scenario"><span class="step">4</span><span>Run the controlled unapproved-client scenario.</span></div></article><article class="panel" style="grid-column:span 2"><div class="kicker">Latest local IDS alerts</div><div class="alerts" id="alerts"><div class="muted">Loading alerts...</div></div></article></section></main><script>function pct(v){return Number.isFinite(Number(v))?Number(v).toFixed(1)+'%':'Waiting'}function esc(v){const d=document.createElement('div');d.textContent=String(v??'');return d.innerHTML}function telemetry(item,id,meta){document.getElementById(id).textContent=item?pct(item.value):'Waiting';document.getElementById(meta).textContent=item?'Sequence '+(item.sequence??'--')+' | '+(item.timestamp??''):'No telemetry received'}async function refresh(){try{const data=await (await fetch('/api/overview')).json();telemetry(data.telemetry['process-simulator'],'process','processMeta');telemetry(data.telemetry['dnp3-outstation'],'dnp3','dnp3Meta');document.getElementById('count').textContent=data.alerts.length;document.getElementById('countMeta').textContent=data.alerts.length?'Most recent local security events':'No alerts in the local feed';const root=document.getElementById('alerts');root.innerHTML=data.alerts.length?data.alerts.map(a=>'<div class="alert '+esc(a.severity)+'"><div class="rule">'+esc(a.rule_id)+'</div><div>'+esc(a.sensor)+' | '+esc(a.source)+' | '+esc(a.protocol)+'</div><div class="muted">'+esc(a.evidence&&a.evidence.reason||a.evidence&&a.evidence.signature||a.timestamp)+'</div></div>').join(''):'<div class="muted">No local alerts yet.</div>'}catch(e){document.getElementById('alerts').textContent='Console data unavailable'}}refresh();setInterval(refresh,2000);</script></body></html>"""


def recent_alerts(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with open(ALERT_PATH, "rb") as stream:
            content = stream.read()[-524288:]
    except FileNotFoundError:
        return []
    alerts: list[dict[str, Any]] = []
    for line in content.decode("utf-8", errors="ignore").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            alerts.append(event)
    return list(reversed(alerts[-limit:]))


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/overview":
            with latest_lock:
                payload = {"telemetry": dict(telemetry_by_source), "alerts": recent_alerts()}
            self.send_json(HTTPStatus.OK, payload)
            return
        if self.path == "/api/state":
            with latest_lock:
                self.send_json(HTTPStatus.OK, dict(latest))
            return
        if self.path == "/":
            encoded = PAGE.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        if self.path == "/demo":
            encoded = DEMO_PAGE.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/command":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 1024:
                raise ValueError("command body is too large")
            command = json.loads(self.rfile.read(size))
            if not isinstance(command, dict) or command.get("command") not in {"set_pump", "set_inlet"} or not isinstance(command.get("value"), bool):
                raise ValueError("invalid command")
            assert mqtt_client is not None
            result = mqtt_client.publish(COMMAND_TOPIC, json.dumps(command), qos=1)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise ValueError("MQTT publish failed")
            self.send_json(HTTPStatus.ACCEPTED, {"accepted": True})
        except (AssertionError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"accepted": False, "reason": str(exc)})

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    global mqtt_client
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ics-lab-hmi")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(HOST, PORT, keepalive=30)
    mqtt_client.loop_start()
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    print(f"HMI listening on http://{HTTP_HOST}:{HTTP_PORT}", flush=True)
    try:
        server.serve_forever()
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()
