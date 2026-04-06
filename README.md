# Real Estate Pipeline and Lease Strategy Simulator

This project implements an OpenEnv-style environment for a real-world real-estate workflow. The agent manages a mixed pipeline of residential and commercial opportunities, qualifies leads, requests missing information, matches properties, and selects the right next step to move deals forward.

## Motivation

Residential sales teams and commercial leasing teams spend real time on lead qualification, follow-up, and conversion strategy. This environment simulates that operational work rather than a game. The agent is rewarded for actions that improve pipeline quality and expected revenue, and penalized for poor-fit recommendations, premature advancement, or wasteful behavior.

## Environment

The environment class is `RealEstatePipelineEnv` in [real_estate_pipeline/env.py](c:\Users\Lenovo\Desktop\Hackathon\openenv-subopt\real_estate_pipeline\env.py). It implements:

- typed Pydantic `Observation`, `Action`, and `Reward` models
- `reset()` returning the initial observation
- `step(action)` returning observation, reward, done, and info
- `state()` returning the current internal state

Metadata is defined in [openenv.yaml](c:\Users\Lenovo\Desktop\Hackathon\openenv-subopt\openenv.yaml).

## Action Space

Supported actions:

- `classify_opportunity`
- `set_priority`
- `request_missing_info`
- `recommend_property`
- `schedule_visit`
- `move_to_nurture`
- `recommend_lease_terms`
- `advance_stage`
- `drop_opportunity`

Each action is validated by the typed [models.py](c:\Users\Lenovo\Desktop\Hackathon\openenv-subopt\real_estate_pipeline\models.py) schema.

## Observation Space

Each observation includes:

- `task_id`
- `step_count`
- `remaining_steps`
- `queue`
- `active_opportunity`
- `inventory_snapshot`
- `business_rules`
- `available_actions`
- `last_action_result`

## Tasks

The environment ships with three graded tasks:

1. `residential_buyer_qualification` — easy
2. `residential_missing_info_followup` — medium
3. `commercial_lease_strategy` — hard

Task fixtures live in [real_estate_pipeline/fixtures](c:\Users\Lenovo\Desktop\Hackathon\openenv-subopt\real_estate_pipeline\fixtures).

## Reward Design

The reward function provides partial progress signals across the trajectory:

- correct classification
- correct priority
- correct missing-information handling
- correct property matching
- correct stage progression
- credible commercial lease terms

It penalizes:

- invalid actions
- poor-fit recommendations
- unrealistic lease terms
- unnecessary extra steps

Final task success is measured by deterministic graders in [graders.py](c:\Users\Lenovo\Desktop\Hackathon\openenv-subopt\real_estate_pipeline\graders.py), which return a normalized score in `[0.0, 1.0]`.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Locally

Start the API:

```bash
uvicorn app:app --host 0.0.0.0 --port 7860
```

Useful endpoints:

- `GET /`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /tasks`
- `GET /cab/providers`
- `POST /cab/bookings/preview`
- `POST /cab/bookings`
- `GET /simulate/live-example`
- `POST /simulate/live`
- `GET /simulate/live/stream`
- `GET /dashboard/live`

## Live Traffic Simulator

The repo now includes a small CRM-style traffic simulator for demoing how an autonomous agent would process real inbound leads outside the fixed benchmark tasks.

The default live example models this flow:

- a buyer asks for a 2BHK in Whitefield within 95 lakhs
- the agent classifies the lead as a residential buyer
- the agent sets priority to high
- the agent recommends the best-fit listing
- the agent schedules a visit

Run the built-in example:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/simulate/live-example" -Method Get
```

Or submit your own simulated CRM lead:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/simulate/live" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "leads": [
      {
        "lead_id": "live_res_001",
        "customer_name": "Aarav Mehta",
        "inquiry": "Looking for a 2BHK apartment in Whitefield. Budget is 95 lakhs and I want to move in within 30 days. Please suggest options.",
        "segment": "residential",
        "budget": 9500000,
        "location": "Whitefield",
        "timeline_days": 30,
        "property_type": "2BHK apartment",
        "missing_fields": []
      }
    ]
  }'
```

The response includes:

- the action trace chosen by the autonomous agent
- per-step rewards
- the final opportunity state
- the final grader score

## Streaming Demo

For a more presentation-friendly demo, the app can stream multiple inbound leads like a CRM queue.

Browser dashboard:

```powershell
Start-Process "http://127.0.0.1:7860/dashboard/live"
```

Raw NDJSON stream:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:7860/simulate/live/stream?delay_seconds=0.35"
```

Terminal streamer without using the API:

```powershell
python scripts\stream_live_traffic.py --delay-seconds 0.5
```

The stream includes:

- `run_started`
- `lead_received`
- `lead_step`
- `lead_completed`
- `run_completed`

## Cab Booking Verification

The residential flow includes builder-side cab support and cab booking. The repo now exposes a verification layer so you can distinguish between:

- local simulated booking for demos
- Uber deep-link handoff
- Ola partner or corporate onboarding
- Rapido partner or corporate onboarding

Inspect the verified provider matrix:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/cab/providers" -Method Get
```

Preview what a live handoff would look like:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/cab/bookings/preview" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "provider": "uber",
    "pickup_location": "Marathahalli",
    "drop_location": "Whitefield",
    "rider_name": "Aarav Mehta",
    "mode": "auto"
  }'
```

Run an explicit simulated booking for the demo:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/cab/bookings" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{
    "provider": "uber",
    "pickup_location": "Marathahalli",
    "drop_location": "Whitefield",
    "rider_name": "Aarav Mehta",
    "mode": "simulate"
  }'
```

## Fine-Tuning Prep

The repo now includes:

- a reusable policy/scoring layer in `real_estate_pipeline/policy.py`
- a softer partial-match grader in `real_estate_pipeline/graders.py`
- synthetic JSONL export for supervised tuning experiments
- 100+ deterministic synthetic leads across residential and commercial segments
- separate noisy and ambiguous evaluation fixtures in `real_estate_pipeline/eval_fixtures`

Generate step-level training data:

```powershell
python scripts\generate_training_data.py --mode step --output artifacts\training_steps.jsonl
```

Generate task-level training data:

```powershell
python scripts\generate_training_data.py --mode task --output artifacts\training_tasks.jsonl
```

Train lightweight baseline classifiers for category and next-action prediction:

```powershell
python scripts\train_baseline_models.py --input artifacts\training_steps.jsonl --output-dir artifacts\models
```

The exported records include:

- inquiry text
- lead profile
- inventory snapshot
- business rules
- target category, priority, requested fields, property, lease terms, and next stage
- per-step action targets for next-action prediction when using `--mode step`

## Inference

The required inference script is [inference.py](c:\Users\Lenovo\Desktop\Hackathon\openenv-subopt\inference.py). It:

- uses the OpenAI client
- reads `API_BASE_URL`, `MODEL_NAME`, and `HF_TOKEN`
- emits `[START]`, `[STEP]`, and `[END]` logs
- runs all 3 tasks and prints an overall average

Example:

```bash
export HF_TOKEN=...
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
python inference.py
```

## Baseline Scores

The scripted baseline policy targets deterministic fixture-optimal actions. Expected grader scores are approximately:

- `residential_buyer_qualification`: `1.00`
- `residential_missing_info_followup`: `1.00`
- `commercial_lease_strategy`: `1.00`

Average expected score: `1.00`

## Docker

Build and run:

```bash
docker build -t real-estate-pipeline-openenv .
docker run -p 7860:7860 real-estate-pipeline-openenv
```

The container serves the FastAPI app on port `7860`.

## Hugging Face Spaces

This repo is intended for Docker-based Hugging Face Spaces deployment. The Space should be tagged with `openenv` and expose the FastAPI service so validators can ping `/reset`.

## Validation

Recommended checks before submission:

```bash
docker build .
python inference.py
openenv validate
```

If you want an automated helper, use [scripts/validate-submission.sh](c:\Users\Lenovo\Desktop\Hackathon\openenv-subopt\scripts\validate-submission.sh).
