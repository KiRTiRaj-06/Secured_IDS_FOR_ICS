# Experiment Procedure

Use one new `run_id` for each benign or attack session. Create a manifest before running the session, record the scenario configuration, and preserve all resulting evidence files.

1. Create a run manifest with `docker compose run --rm detector python -m ics_ids.run_manifest --run-id <id> --scenario <scenario>`. The Compose detector stores it in `data/manifests/`.
2. Run the selected isolated scenario with the same ID.
3. Save any PCAP and record its path in the run manifest after capture.
4. Analyze PCAP with the offline Zeek/Suricata script when available.
5. Run `python -m ics_ids.evaluate_alerts --scenario scenarios/<scenario>.json --alerts output/alerts.jsonl`.
6. For ML, collect independent runs for each scenario, then train using `python -m ics_ids.train_model` and retain `reports/model-metrics.json`.
7. After the run set is complete, generate the evidence summary with `python -m ics_ids.evaluate_experiments`. It records rule coverage, benign alert counts, and same-run detection delay without inferring unsupported metrics.

Only compare measurements from runs with the same policy version, software configuration, and traffic generation settings. Benign runs must be collected independently of attack runs.
