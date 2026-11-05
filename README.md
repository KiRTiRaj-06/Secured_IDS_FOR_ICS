# Secure ICS IDS

This is an isolated laptop-based ICS security laboratory. It combines a simulated tank and soft PLC, a DNP3 master/outstation path, MQTT telemetry, ML dataset scoring, signature-based network monitoring, and Wazuh alert ingestion. It must only be used with the included simulated services and offline datasets.

## Requirements

- Docker Desktop with the WSL 2 backend on Windows, or Docker Engine and Compose on Linux.
- Git.
- Internet access for the first image and Python dependency download.

The base Compose network is internal to the lab. The optional HMI profile publishes
only `127.0.0.1:8090`, so it is reachable from this laptop but not the LAN.

## Live laptop lab: process and HMI

This demonstration slice simulates a tank process and a small
software PLC inside Docker, with an operator HMI at `http://localhost:8090`.
The HMI can only toggle a simulated inlet and pump. It cannot reach real PLCs
or issue DNP3 commands. The process publishes `tank_level_pct` through the
same MQTT topic the IDS already monitors.

Run from PowerShell:

```powershell
docker compose build
docker compose --profile live up -d mosquitto detector process-simulator hmi
Start-Process http://localhost:8090
docker compose logs -f process-simulator detector
```

Use the two controls in the HMI and watch the level change. The normal process
should not create IDS alerts. To stop this live slice:

```powershell
docker compose --profile live down
```

For the presentation, describe this accurately as **Level 0/1 process and
soft-PLC simulation**, with the HMI at the operator layer. The live DNP3
master/outstation pair and passive DNP3 network sensor are included below.

## Live MQTT network IDS

The `nids` profile attaches Suricata to the broker's network namespace. It
inspects packets that reach the real Mosquitto broker, writes EVE JSON, then a
small follower normalizes only signature alerts into `output/alerts.jsonl` for
Wazuh. It does not block or alter traffic.

```powershell
docker compose --profile live --profile nids up -d
docker compose --profile live --profile nids logs -f suricata-live sensor-follower
```

With the HMI open, toggle an operator control once. The current laboratory rule
detects the MQTT command topic and creates `SURICATA-9000002`. Add or update the
Suricata rules in `config/wazuh/local_rules.xml` on the Wazuh manager, restart
the manager, and search Wazuh for `data.sensor: "suricata"`.

## Live DNP3 master/outstation lab

The `dnp3-live` profile adds a software DNP3 outstation on the private Docker
network and a separate DNP3 master/gateway. The outstation changes analog input
point `0`; the gateway performs DNP3 polls and publishes the returned value as
`tank_level_pct` to the existing MQTT detector. No DNP3 port is exposed to the
host or LAN.

```powershell
docker compose --profile live --profile dnp3-live up -d
docker compose --profile live --profile dnp3-live logs -f dnp3-outstation dnp3-live-gateway
```

## Live DNP3 network inspection

Start the passive DNP3 sensor alongside the live lab:

```powershell
docker compose --profile live --profile dnp3-live --profile nids up -d
```

## Generate project evidence

Create a repeatable Markdown and JSON summary of the local alerts and any saved
MQTT/DNP3 model metrics. This is useful for the final report and presentation.

```powershell
docker compose run --rm detector python -m ics_ids.generate_project_report `
  --alerts /var/log/ics-ids/alerts.jsonl `
  --mqtt-metrics /reports/mqtt-model-metrics.json `
  --dnp3-metrics /reports/dnp3-model-metrics.json `
  --output /reports/project-evidence.md `
  --json-output /reports/project-evidence.json
```

The generated files are `reports/project-evidence.md` and
`reports/project-evidence.json`. Missing metric files are reported as unavailable
instead of making the command fail.

## Evaluate controlled experiment runs

The plan requires evaluation beyond one dashboard screenshot. Create a manifest
before each independent scenario run, keep the same `RUN_ID` in the simulator,
then generate a per-run report after collecting the evidence:

```powershell
docker compose run --rm detector python -m ics_ids.run_manifest --run-id benign-003 --scenario benign
docker compose run --rm detector python -m ics_ids.evaluate_experiments `
  --manifests /data/manifests `
  --events /var/log/ics-ids/events.jsonl `
  --alerts /var/log/ics-ids/alerts.jsonl `
  --output /reports/experiment-evaluation.md `
  --json-output /reports/experiment-evaluation.json
```

This reports expected-rule coverage, benign alerts per run, and same-run
detection delay. Dataset-model precision, recall, F1, and confusion matrices
remain in the saved MQTT/DNP3 metric files; the report does not invent those
metrics from unlabeled live traffic.

The DNP3 master connects through an in-lab transparent TCP relay. Suricata
observes the relay interface and `dnp3-sensor-follower` writes its signature
alerts to `output/alerts.jsonl` for the existing Wazuh agent. The relay does
not modify packets and the setup is for local laboratory traffic only.

## Controlled unapproved-master demonstration

With the live DNP3 and NIDS profiles already running, launch the read-only
lab client once:

```powershell
docker compose --profile dnp3-attack run --rm dnp3-rogue-master
```

It briefly connects to the DNP3 relay without sending a DNP3 request or issuing
any control operation. The relay allowlist accepts only `dnp3-live-gateway`,
appends `OT-DNP3-UNAUTHORIZED-SOURCE-001` to
`output/alerts.jsonl`, and the Wazuh rule maps it to level 12.

## Demonstration console

Open the local presentation view while the `live` profile is running:

```text
http://127.0.0.1:8090/demo
```

It shows both live telemetry streams, the latest local IDS evidence, and the
recommended demonstration sequence. The original HMI remains at `/`.

This needs its first image build to download and compile the Apache-licensed
OpenDNP3 Python binding. The DNP3 gateway does not issue control commands; it
only reads analog input point `0`. Stop it with:

```powershell
docker compose --profile live --profile dnp3-live stop dnp3-outstation dnp3-live-gateway
```

## Start the benign telemetry slice

From this directory:

```powershell
docker compose build
docker compose up -d mosquitto detector
docker compose --profile sim run --rm -e SCENARIO=benign -e RUN_ID=benign-001 -e MAX_MESSAGES=20 simulator
Get-Content .\output\alerts.jsonl
```

The expected result is a running MQTT broker and detector, 20 local telemetry messages, and no range/rate alerts for the benign scenario. Stop long-running services with `docker compose down`.

The simulator also appends raw synthetic events to `output/events.jsonl`. Run separate scenario sessions with unique run IDs so the dataset split can keep entire sessions together:

```powershell
docker compose --profile sim run --rm -e SCENARIO=benign -e RUN_ID=benign-002 -e MAX_MESSAGES=80 simulator
docker compose --profile sim run --rm -e SCENARIO=fdi -e RUN_ID=fdi-002 -e MAX_MESSAGES=80 simulator
docker compose --profile sim run --rm -e SCENARIO=replay -e RUN_ID=replay-002 -e MAX_MESSAGES=80 simulator
docker compose --profile sim run --rm -e SCENARIO=flood -e RUN_ID=flood-002 -e MAX_MESSAGES=80 simulator
docker compose run --rm detector python -m ics_ids.train_model /var/log/ics-ids/events.jsonl --model /models/random-forest.joblib
```

Training requires at least three independent runs per label as a practical starting point; the script groups by `run_id`, keeps groups intact across the train/test split, and stops if the split lacks both classes. It writes per-class metrics and the exact train/test run IDs to `reports/model-metrics.json`. This synthetic dataset demonstrates the pipeline only and cannot support claims about production ICS traffic.

## DNP3 dataset model

The project includes an offline multiclass DNP3 trainer for the supplied `DNP3_Intrusion_Detection_Dataset_Final` data. It uses the prepared `Custom_DNP3_Parser` train/test split because it includes DNP3-aware features such as request and response function codes, master/slave packet counts, and per-layer traffic summaries.

The baseline algorithm is scikit-learn's `RandomForestClassifier`: 300 decision trees vote on the attack class. This is a supervised learning baseline, not a deep-learning model. It was selected because it works well with tabular numeric features, handles non-linear relationships, supports multiclass labels, and supplies feature-importance values for a defensible explanation. Missing numeric values are replaced with each training column's median. The trainer deliberately excludes flow IDs, addresses, ports, timestamps, and direction identifiers, because these can create misleadingly high accuracy by leaking capture-specific details.

The supplied split is retained for reproducibility. It demonstrates performance against this dataset but is not evidence of performance on a new industrial site or live production traffic.

Run from PowerShell, adjusting the two dataset paths only if you move the source dataset:

```powershell
$dnp3 = 'D:\Program_FILes\Minor_Pro_S7\again\ids-ics-project\DNP3_Intrusion_Detection_Dataset_Final\Training_Testing_Balanced_CSV_Files\Custom_DNP3_Parser'
docker compose run --rm -v "${dnp3}:/dataset:ro" detector python -m ics_ids.train_dnp3_model --train /dataset/Custom_DNP3_Parser_Training_Balanced.csv --test /dataset/Custom_DNP3_Parser_Testing_Balanced.csv --model /models/dnp3-random-forest.joblib --metrics /reports/dnp3-model-metrics.json
Get-Content .\reports\dnp3-model-metrics.json
```

The command reads the source data as read-only. It saves only the trained model under `models/` and reproducibility evidence under `reports/`.

After training, score a small held-out DNP3 dataset sample and emit only non-normal predictions into `output/alerts.jsonl`, which the existing WSL Wazuh agent already collects. Add the `dnp3-ml` rules from `config/wazuh/local_rules.xml` to the manager before using this in the dashboard.

```powershell
docker compose run --rm -v "${dnp3}:/dataset:ro" detector python -m ics_ids.score_dnp3_flows --input /dataset/Custom_DNP3_Parser_Testing_Balanced.csv --model /models/dnp3-random-forest.joblib --alerts /var/log/ics-ids/alerts.jsonl --limit 100
Get-Content .\output\alerts.jsonl -Tail 5
```

## MQTT dataset model

MQTTset has a separate feature schema, so it is trained as a separate multiclass model. The trainer uses its supplied reduced `train70` and `test30` files, keeps the packet-field schema separate from DNP3, and records the same reproducibility evidence. It uses the same 300-tree Random Forest baseline; MQTT payload and will-message fields are excluded, and infinite/oversized numeric values are treated as missing before median imputation.

```powershell
$mqtt = 'D:\Program_FILes\Minor_Pro_S7\again\ids-ics-project\data\Data\FINAL_CSV'
docker compose run --rm -v "${mqtt}:/dataset:ro" detector python -m ics_ids.train_mqtt_model --train /dataset/train70_reduced.csv --test /dataset/test30_reduced.csv --model /models/mqtt-random-forest.joblib --metrics /reports/mqtt-model-metrics.json
Get-Content .\reports\mqtt-model-metrics.json
```

Add the `mqtt-ml` rules from `config/wazuh/local_rules.xml` to the manager and restart it. Then score a bounded test sample; non-legitimate predictions append to the existing Wazuh-collected alert file.

```powershell
docker compose run --rm -v "${mqtt}:/dataset:ro" detector python -m ics_ids.score_mqtt_packets --input /dataset/test30_reduced.csv --model /models/mqtt-random-forest.joblib --alerts /var/log/ics-ids/alerts.jsonl --limit 500
```

## Offline PCAP analysis

Save a PCAP from an authorized lab capture, then run from PowerShell:

```powershell
.\scripts\run-pcap-analysis.ps1 -Pcap .\path\to\capture.pcap -AuthorizedDnp3Sources "172.28.0.10"
```

The script builds a Zeek image with the CISA ICSNPP DNP3 package, runs Zeek and Suricata offline, and normalizes their findings into `output/alerts.jsonl`. The DNP3 source allowlist enables an alert for recognised operational controls, including OPERATE, restart, stop, initialize, and disable-unsolicited commands, from an unapproved source. Supply the IP address visible in `source_h` or `id.orig_h`; without an allowlist, this rule is disabled. Outputs are also retained in timestamped folders in `output/`. On first use, Docker must download the base images and the Zeek package build needs internet access.

Repeated control records from one offline PCAP are grouped into one alert per source, destination, and function code. The alert evidence includes `occurrence_count`, `first_observed`, and `last_observed`, avoiding a dashboard alert flood while preserving the attack volume.

## Wazuh integration templates

- `config/wazuh/agent-localfile.xml` is the agent-side JSON file collection block. The file must be available at `/var/log/ics-ids/alerts.jsonl` on the Linux host running the agent.
- `config/wazuh/local_rules.xml` contains manager-side rules. Merge these rules into the manager's local rules file, keep rule IDs unique, validate with `wazuh-logtest`, and restart the manager according to the installed Wazuh version.
- A Docker volume on Windows is not automatically visible to an Ubuntu Wazuh VM. Use an approved shared folder or forward alerts over a private lab network; do not expose the dashboard or collector publicly.

## Security configuration

The default broker configuration is intentionally limited to the private Docker development network. Before any presentation outside that environment, switch to the TLS and password template in `config/mosquitto-secure.conf` and follow [security-baseline.md](docs/security-baseline.md). The detector is passive and never sends DNP3 commands or blocks traffic.

## Controlled detector scenarios

```powershell
docker compose --profile sim run --rm -e SCENARIO=fdi -e RUN_ID=fdi-001 -e MAX_MESSAGES=12 simulator
docker compose --profile sim run --rm -e SCENARIO=replay -e RUN_ID=replay-001 -e MAX_MESSAGES=12 simulator
docker compose --profile sim run --rm -e SCENARIO=flood -e RUN_ID=flood-001 -e MAX_MESSAGES=100 simulator
```

These exercise only synthetic MQTT telemetry and do not represent DNP3 attacks. The flood profile is bounded by `MAX_MESSAGES`; keep it on the private Compose network.

## Current detector behavior

- `OT-RANGE-001`: point value outside the configured 0-100% range.
- `OT-RATE-001`: point changes by more than 20 percentage points between messages.
- `OT-REPLAY-001`: sequence number does not increase.
- `OT-FLOOD-001`: more than 10 messages for one point within 2 seconds (configurable with `RATE_LIMIT_MESSAGES` and `RATE_WINDOW_SECONDS`).
- `OT-ML-001`: optional Random Forest classification after `models/random-forest.joblib` has been trained and mounted.
- Alerts append to `output/alerts.jsonl`, ready for later Wazuh file collection.

Thresholds are demonstration defaults, not calibrated process safety limits. The
live process simulator uses MQTT only. Offline DNP3 PCAP analysis with Zeek and
Suricata, dataset scoring, ML alert normalization, and Wazuh ingestion are
implemented separately; they are not proof of protection for a production site.

## Project progression

1. Demonstrate the isolated MQTT slice and local live HMI/process simulation.
2. Add a real DNP3 master/outstation and validate normal polling through the DNP3-to-MQTT gateway.
3. Add live passive monitoring or an in-line DNP3 tap to the DNP3 path; retain PCAP replay as repeatable evidence.
4. Extend run manifests and scenario evaluation for the complete live demonstration.

## Project files

- `src/gateway.py` and `src/dnp3_adapter.py`: DNP3-to-MQTT gateway boundary.
- `config/ids-policy.json`: point ranges, maximum change, and rate policy.
- `scenarios/`: expected alert behavior for each controlled scenario.
- `src/run_manifest.py` and `src/evaluate_alerts.py`: repeatable experiment evidence and scenario result summaries.
- `config/zeek/` and `config/suricata/`: project-specific passive sensor configuration assets.
- `config/wazuh/`: Wazuh agent collection and manager rule templates.
