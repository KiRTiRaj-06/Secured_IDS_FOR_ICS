# Implementation Audit Against the Project Plans

## Completed Core Work

- Isolated Docker lab with a soft process, MQTT broker, DNP3 outstation, DNP3
  master/gateway, and localhost-only HMI.
- Passive network visibility: live Suricata monitoring of MQTT and DNP3 lab
  traffic, plus offline Zeek with ICSNPP DNP3 and Suricata PCAP analysis.
- Structured JSONL alerts, Wazuh agent collection, manager rules, and dashboard
  searches for process, network, and ML evidence.
- Four controlled detector cases: telemetry replay, false-data/range violation,
  bounded flood, and a lab-only unapproved DNP3 source event. The latter does
  not issue a DNP3 control command.
- Random Forest baselines for the supplied MQTT and DNP3 datasets, with saved
  classification reports, confusion matrices, feature importance, and accuracy.
- ATT&CK-for-ICS context for the deterministic replay, false-data, and flood
  rules, retained as structured alert metadata.
- A local demo console and reproducible project-evidence report.

## Remaining Core Evaluation Work

- Run several independent benign and scenario sessions using unique manifests,
  then generate `reports/experiment-evaluation.md`. This records expected-rule
  coverage, benign alerts per run, and same-run detection delay.
- Preserve the produced manifests, alert JSONL, model metrics, PCAPs, and Wazuh
  screenshots as final-report evidence.
- State the current boundary honestly: live ML scoring is not implemented because
  the supplied dataset feature schemas cannot be derived from the small live lab
  packet streams without a separately validated feature-extraction pipeline.

## Deliberately Deferred Stretch Work

- XGBoost comparison, SHAP explanations, and LSTM/CNN sequence models.
- Production TLS/authentication deployment and MQTT credential management.
- Real PLCs, real plant traffic, inline blocking, cloud deployment, and multi-site
  emulation.

These items are stretch or future-scope work in the technical plan. They should
not be represented as implemented without separate data collection and testing.
