from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from real_estate_pipeline.training_data import build_step_training_records, build_task_training_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export synthetic and fixture-derived training records to JSONL.")
    parser.add_argument(
        "--output",
        default="artifacts/training_steps.jsonl",
        help="Output JSONL file path.",
    )
    parser.add_argument(
        "--mode",
        choices=["step", "task"],
        default="step",
        help="Whether to export one record per decision step or one record per task.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = build_step_training_records() if args.mode == "step" else build_task_training_records()
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    print(f"Wrote {len(records)} training records to {output_path}", flush=True)


if __name__ == "__main__":
    main()
