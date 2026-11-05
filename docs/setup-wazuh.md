# Wazuh Integration

Install Wazuh all-in-one on an Ubuntu VM or Linux host using the current official Wazuh Quickstart. Use the templates in `config/wazuh` after the server and a sensor-side agent are operating.

1. Make the project's curated alert file available on the Linux sensor as `/var/log/ics-ids/alerts.jsonl`.
2. Merge `config/wazuh/agent-localfile.xml` into the agent configuration's `ossec_config` section.
3. Merge `config/wazuh/local_rules.xml` into the Wazuh manager local rules file, checking that its rule IDs do not conflict with existing local rules.
4. Validate example JSON through `wazuh-logtest` before restarting the manager.
5. Restart the relevant Wazuh agent and manager services using the commands appropriate to the installed version.
6. In the dashboard, create saved searches for:
   - `rule.groups: ics_ids` for all project events.
   - `data.sensor: python-ids` for process-policy alerts.
   - `data.sensor: "mqtt-ml" OR data.sensor: "dnp3-ml"` for dataset-model results.
   - `data.sensor: suricata` for live MQTT/DNP3 signature observations.
   - `data.sensor: "dnp3-tap"` for the controlled, lab-only unapproved-source scenario.
   - `data.sensor: zeek-icsnpp-dnp3` for offline DNP3 PCAP analysis.

The collector receives only curated alerts by default. Keep raw PCAP and full
Zeek/Suricata logs on the sensor for evidence and troubleshooting, then forward
selected summaries after volume and retention needs are measured. The NIDS is
passive: it observes the Docker lab traffic and does not expose OT services to the
host LAN or send control traffic.
