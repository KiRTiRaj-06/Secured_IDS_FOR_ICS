# Wazuh Configuration Assets

`agent-localfile.xml` configures the Linux Wazuh agent to collect the curated `alerts.jsonl` file.

`local_rules.xml` assigns Wazuh levels and descriptions to project alert IDs. Use `wazuh-logtest` with a representative JSON line before deploying rule changes.

These files are templates. Merge their contents into the corresponding configuration files of the installed Wazuh version; do not replace whole Wazuh configuration files.
