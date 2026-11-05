"""Create one immutable manifest per experiment run."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", type=Path, default=Path(os.getenv("MANIFEST_PATH", "data/manifests")))
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    manifest = {
        "schema_version": 1,
        "run_id": args.run_id,
        "scenario": args.scenario,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "notes": args.notes,
        "artifacts": {
            "events": f"output/events-{args.run_id}.jsonl",
            "alerts": f"output/alerts-{args.run_id}.jsonl",
            "pcap": None,
            "zeek_log_directory": None,
            "suricata_log_directory": None,
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / f"{args.run_id}.json"
    if destination.exists():
        raise SystemExit(f"Manifest already exists: {destination}")
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
