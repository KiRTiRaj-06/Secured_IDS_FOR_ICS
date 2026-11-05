# Dataset Data Dictionary

| Field | Source | Meaning |
|---|---|---|
| `run_id` | Simulator or gateway | One independent experiment session. All rows from a run stay in one split. |
| `scenario` | Scenario manifest | `benign`, `fdi`, `replay`, or `flood` for synthetic telemetry. |
| `timestamp` | Publisher | UTC time at event production. |
| `point` | Gateway/simulator | Stable process-point name. |
| `value` | Gateway/simulator | Point measurement in the point's declared unit. |
| `sequence` | Gateway/simulator | Monotonic sequence expected to increase for a point within a run. |
| `value_delta` | Dataset builder | Difference from the previous point value in the same run. |
| `sequence_delta` | Dataset builder | Difference from the previous sequence in the same run. |
| `interarrival_seconds` | Dataset builder | Time since prior message for that point and run. |
| `label` | Dataset builder | `0` for benign, `1` for a labeled attack scenario. |

Raw PCAPs, Zeek logs, Suricata EVE files, and alert JSONL are evidence records. They must retain their run ID and timestamps but are not merged by row with a model dataset until the alignment method is documented.
