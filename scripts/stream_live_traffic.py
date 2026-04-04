from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from real_estate_pipeline.live_simulator import DEFAULT_STREAM_LEADS, stream_live_traffic_events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream simulated CRM leads through the autonomous real-estate agent.")
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.5,
        help="Delay between agent steps so the stream feels live in the terminal.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for raw_event in stream_live_traffic_events(DEFAULT_STREAM_LEADS, delay_seconds=max(args.delay_seconds, 0.0)):
        event = json.loads(raw_event)
        event_type = event["event"]
        lead_id = event.get("lead_id") or "-"
        payload = event["payload"]

        if event_type == "run_started":
            print(f"[RUN] starting stream for {payload['processed_leads']} inbound leads", flush=True)
        elif event_type == "lead_received":
            print(f"[LEAD] {lead_id} received: {payload['customer_name']}", flush=True)
            print(f"       inquiry: {payload['inquiry']}", flush=True)
        elif event_type == "lead_step":
            action = payload["action"]["action_type"]
            score = payload["grader_score"]
            print(f"[STEP] {lead_id} step={payload['step']} action={action} score={score:.2f}", flush=True)
            print(f"       thought: {payload['thought']}", flush=True)
        elif event_type == "lead_completed":
            print(
                f"[DONE] {lead_id} stage={payload['final_stage']} score={payload['final_score']:.2f} property={payload['recommended_property_id']}",
                flush=True,
            )
        elif event_type == "run_completed":
            print(f"[RUN] completed {payload['processed_leads']} leads", flush=True)


if __name__ == "__main__":
    main()
