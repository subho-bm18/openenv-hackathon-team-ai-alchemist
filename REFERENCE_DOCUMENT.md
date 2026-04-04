# Reference Document
## Project: Real Estate Pipeline and Lease Strategy Simulator

## 1. Purpose

This document defines the reference specification for the selected OpenEnv project:

**Real Estate Pipeline and Lease Strategy Simulator**

The project simulates a real-world real-estate operations workflow where an agent handles:

- residential lead qualification and follow-up
- commercial tenant qualification
- property matching
- lease progression and negotiation strategy

The purpose of the environment is to evaluate how well an agent can make structured, business-relevant decisions that maximize conversion quality and expected revenue while respecting workflow rules and realistic market constraints.

---

## 2. Project Summary

### 2.1 Problem Statement

Real-estate teams spend significant time qualifying inbound leads, identifying serious prospects, requesting missing details, matching opportunities to inventory, and moving prospects to the correct next stage. Residential and commercial real-estate pipelines differ in complexity, but both require human judgment, prioritization, and structured follow-up.

This environment simulates that real-world task as an OpenEnv environment.

### 2.2 Selected Idea

The selected idea merges:

- **Residential - Real Estate Lead Qualification and Follow-Up Simulator**
- **Commercial - Lease Negotiation Strategy Simulator**

into a single unified environment where the agent manages a mixed real-estate opportunity pipeline.

### 2.3 Real-World Role Simulated

The agent acts as a:

- real-estate pipeline coordinator
- inside sales associate
- leasing operations analyst
- broker support associate

This is a real-world business role and not a game or toy workflow.

---

## 3. Scope

### 3.1 In Scope

- qualification of residential buyer or renter leads
- follow-up decisions for residential opportunities
- qualification of commercial tenant inquiries
- matching leads to residential or commercial inventory
- recommending next-step commercial lease strategy
- scheduling visits or advancing opportunities
- requesting missing information
- prioritizing high-value opportunities
- reward-based evaluation of pipeline decisions

### 3.2 Out of Scope

- full legal lease drafting
- full mortgage underwriting
- free-form human chat simulation without structured actions
- full CRM implementation
- payment processing
- property listing generation

---

## 4. Key Requirements

The system must satisfy the following key requirements.

### 4.1 Real-World Task Simulation

The environment must simulate a task that humans actually perform in real-estate operations.

The selected project satisfies this by simulating:

- residential lead qualification
- follow-up management
- commercial tenant pipeline handling
- lease progression strategy

### 4.2 Full OpenEnv Compliance

The project must implement the OpenEnv interface and artifacts, including:

- typed Pydantic `Observation` model
- typed Pydantic `Action` model
- typed Pydantic `Reward` model
- `reset() -> Observation`
- `step(action) -> observation, reward, done, info`
- `state() -> dict | structured state model`
- `openenv.yaml`

The environment must be designed to pass `openenv validate`.

### 4.3 Minimum 3 Tasks With Agent Graders

The project must include at least 3 tasks:

- easy
- medium
- hard

Each task must include a deterministic agent grader that returns a score between `0.0` and `1.0`.

### 4.4 Meaningful Reward Function

The reward design must provide intermediate signal over the trajectory, not just a binary final outcome.

The reward must:

- reward partial progress
- reward correct classification and prioritization
- reward correct property matching
- reward valid next-step decisions
- penalize invalid, repetitive, or harmful actions

### 4.5 Baseline Inference Script

The project must include a reproducible baseline inference script that:

- uses the OpenAI API client
- reads `OPENAI_API_KEY` from environment variables
- runs a selected model on all tasks
- outputs per-task scores and average score

### 4.6 Deployment and Packaging

The environment must include:

- a working `Dockerfile`
- support for containerized execution
- deployment support for Hugging Face Spaces
- tagging and packaging suitable for an `openenv` HF Space

### 4.7 Documentation

The project must include a `README.md` that documents:

- environment description
- real-world motivation
- action space
- observation space
- task descriptions
- setup instructions
- usage instructions
- baseline scores

---

## 5. Functional Requirements

### FR-1 Real-World Workflow Simulation

The system shall simulate a realistic real-estate operations pipeline involving residential and commercial opportunities.

### FR-2 Opportunity Queue Management

The system shall maintain an opportunity queue containing one or more active opportunities.

Each opportunity shall include structured metadata such as:

- lead type
- segment
- intent
- location preferences
- budget or rent range
- urgency
- missing information
- customer message history

### FR-3 Residential Lead Qualification

The system shall support residential opportunity workflows including:

- lead classification
- priority assignment
- follow-up recommendation
- listing recommendation
- visit scheduling
- nurture handling

### FR-4 Commercial Leasing Workflow

The system shall support commercial opportunity workflows including:

- tenant qualification
- commercial property matching
- lease strategy recommendation
- negotiation-stage advancement
- escalation to leasing manager when required

### FR-5 Structured Observation Model

The system shall expose a typed `Observation` model with sufficient information for agent decision-making.

The observation should include:

- task metadata
- queue state
- active opportunity
- inventory snapshot
- business rules
- available actions
- previous action outcome
- remaining step budget

### FR-6 Structured Action Model

The system shall expose a typed `Action` model for all valid environment operations.

Supported action families shall include:

- queue management actions
- lead qualification actions
- follow-up actions
- property matching actions
- residential pipeline actions
- commercial lease strategy actions

### FR-7 Reward Model

The system shall expose a typed `Reward` model containing:

- numeric reward value
- reward components
- progress notes
- penalty notes

### FR-8 `reset()` Behavior

The system shall implement `reset()` to initialize a fresh task episode and return the initial observation.

### FR-9 `step()` Behavior

The system shall implement `step(action)` to:

- validate the action
- apply the action to environment state
- update opportunity and pipeline state
- compute reward
- determine done status
- return observation, reward, done, and info

### FR-10 `state()` Behavior

The system shall implement `state()` to return the current internal environment state for debugging and evaluation purposes.

### FR-11 Task Set

The system shall include at least 3 concrete tasks.

Recommended task set:

#### Task 1: Easy
**Residential Buyer Lead Qualification**

Expected goal:

- identify a high-intent residential buyer
- assign correct priority
- select a suitable listing
- schedule the correct next action

#### Task 2: Medium
**Residential Lead With Missing Details**

Expected goal:

- identify missing budget, timeline, or financing information
- request the correct missing fields
- keep lead active
- avoid premature listing push

#### Task 3: Hard
**Commercial Lease Opportunity Strategy**

Expected goal:

- identify a strong commercial tenant
- match the best-fit commercial property
- recommend realistic next-step lease terms
- progress the opportunity correctly

### FR-12 Deterministic Agent Graders

Each task shall include a deterministic grader.

Each grader shall:

- accept final environment state and/or action history
- return a score from `0.0` to `1.0`
- use explicit rule-based scoring criteria
- avoid non-deterministic judgment

### FR-13 Partial Progress Rewards

The system shall provide partial rewards for intermediate success signals such as:

- correct classification
- correct prioritization
- correct missing-information detection
- correct property match
- correct progression stage

### FR-14 Penalty Logic

The system shall penalize undesirable behavior such as:

- repeated unnecessary actions
- invalid actions
- poor-fit property recommendations
- unrealistic lease recommendations
- dropping valid leads without cause
- pushing negotiation or visit too early

### FR-15 Baseline Inference

The system shall provide a baseline inference script that:

- iterates through the defined tasks
- uses the OpenAI API client
- reads `OPENAI_API_KEY`
- logs agent actions
- outputs reproducible baseline scores

### FR-16 Validation Support

The system shall include all configuration and metadata necessary for validation using `openenv validate`.

---

## 6. Non-Functional Requirements

### NFR-1 Realism

The environment should feel like a believable real-estate workflow and should avoid toy-like abstractions.

### NFR-2 Determinism

Task fixtures, grader logic, and baseline evaluation should be deterministic enough to make scores reproducible.

This should be achieved through:

- fixed task fixtures
- fixed scoring rules
- stable prompts for baseline runs
- deterministic settings where available

### NFR-3 Performance

The environment should respond quickly to `reset()` and `step()` calls and should not require heavy external services to run locally.

### NFR-4 Maintainability

The codebase should be organized into clear modules such as:

- models
- environment logic
- tasks
- graders
- rewards
- fixtures

### NFR-5 Testability

The environment should support unit and integration tests for:

- model validation
- step transitions
- reward calculation
- grader scoring
- task completion logic

### NFR-6 Containerized Execution

The project must include a working `Dockerfile` and must start successfully with:

- `docker build`
- `docker run`

### NFR-7 Hugging Face Spaces Deployment

The project must be deployable as a containerized Hugging Face Space and should be tagged with `openenv`.

### NFR-8 Documentation Quality

The `README.md` must clearly explain:

- what the environment simulates
- why it is realistic
- action and observation spaces
- task definitions
- setup instructions
- run instructions
- baseline scores

### NFR-9 Reproducibility

The baseline evaluation must produce consistent results on the defined task fixtures when the same model and configuration are used.

### NFR-10 Safety and Robustness

The environment should reject malformed actions gracefully and should expose informative error details in `info` or validation output.

---

## 7. Proposed OpenEnv Model Specification

### 7.1 Observation Model

The `Observation` model should include fields such as:

- `task_id: str`
- `step_count: int`
- `remaining_steps: int`
- `queue: list[OpportunitySummary]`
- `active_opportunity: OpportunityDetail | None`
- `inventory_snapshot: InventorySnapshot`
- `business_rules: list[str]`
- `available_actions: list[str]`
- `last_action_result: str | None`

### 7.2 Action Model

The `Action` model should include fields such as:

- `action_type: str`
- `opportunity_id: str | None`
- `property_id: str | None`
- `priority: str | None`
- `category: str | None`
- `message: str | None`
- `requested_fields: list[str] | None`
- `lease_terms: LeaseTerms | None`
- `metadata: dict | None`

### 7.3 Reward Model

The `Reward` model should include fields such as:

- `value: float`
- `components: dict[str, float]`
- `progress_signals: list[str]`
- `penalties: list[str]`

---

## 8. Task Specification

### 8.1 Easy Task

**Name:** `residential_buyer_qualification`

**Scenario:**
A residential buyer provides clear details including budget, location, and near-term move-in interest.

**Success criteria:**

- correct classification
- correct priority
- appropriate listing recommendation
- correct next-step progression

### 8.2 Medium Task

**Name:** `residential_missing_info_followup`

**Scenario:**
A residential lead gives partial requirements but key details are missing.

**Success criteria:**

- identifies missing details
- requests the correct details
- avoids invalid advancement
- keeps lead active

### 8.3 Hard Task

**Name:** `commercial_lease_strategy`

**Scenario:**
A commercial tenant requires a location, size, budget, and timeline fit, with multiple candidate spaces available.

**Success criteria:**

- correct commercial classification
- strong property fit
- realistic lease strategy
- correct next pipeline stage

---

## 9. Reward Function Reference

The reward function should provide meaningful signal during the full trajectory.

### 9.1 Positive Signals

- correct opportunity classification
- correct urgency or priority assignment
- correct missing-information request
- correct property fit
- correct scheduling or progression step
- realistic lease recommendation
- good revenue-oriented decision

### 9.2 Negative Signals

- invalid or malformed action
- repeated or wasteful action
- wrong property type match
- unrealistic leasing strategy
- incorrect drop or reject decision
- advancing without enough information

### 9.3 Example Reward Weights

- `+0.10` correct classification
- `+0.10` correct priority
- `+0.15` correct missing-information handling
- `+0.20` correct property match
- `+0.20` correct next-step progression
- `+0.25` correct final outcome
- `-0.05` unnecessary action
- `-0.10` poor-fit recommendation
- `-0.15` unrealistic lease recommendation
- `-0.02` per extra step

---

## 10. Baseline Inference Reference

The baseline script should:

- import the environment
- load all tasks
- run each task against a chosen OpenAI model
- convert model outputs into structured actions
- apply those actions using `step()`
- record final scores

### Baseline requirements

- reads `OPENAI_API_KEY` from environment variables
- uses a fixed model name
- uses fixed prompts
- prints per-task score and average score
- produces reproducible output across runs with same configuration

### Example output

```text
Task residential_buyer_qualification: 0.92
Task residential_missing_info_followup: 0.81
Task commercial_lease_strategy: 0.74
Average score: 0.82
```

---

## 11. Deployment Reference

### 11.1 Docker

The project must include a working `Dockerfile` that:

- installs dependencies
- copies project files
- exposes the service entrypoint
- starts cleanly in a container

### 11.2 Hugging Face Spaces

The project must be deployable as a Docker-based Hugging Face Space.

The Space should:

- run the environment or a lightweight demo app
- describe the environment
- support the `openenv` tag

---

## 12. Pre-Submission Checklist

All of the following must pass before submission. Failure on any item may disqualify the project.

### 12.1 HF Space Deploys

The deployed Hugging Face Space must:

- be reachable via its public URL
- respond successfully to an automated ping
- return HTTP `200`
- respond correctly to `POST /reset`

### 12.2 OpenEnv Spec Compliance

The submission must include and validate:

- `openenv.yaml`
- typed models
- `step()`
- `reset()`
- `state()`
- required OpenEnv endpoints and metadata

The environment must pass `openenv validate`.

### 12.3 Dockerfile Builds

The submitted repository must contain a working `Dockerfile` that builds successfully through automated validation.

### 12.4 Baseline Reproduces

The submitted root-level `inference.py` must:

- complete without error
- run all required tasks
- produce scores
- emit the required structured stdout logs

### 12.5 Three or More Tasks With Graders

The submission must:

- enumerate at least 3 tasks
- run each grader successfully
- ensure each grader returns a score in the range `0.0` to `1.0`

### 12.6 Mandatory Environment Variables

Before submission, the following variables must be defined in the runtime configuration:

- `API_BASE_URL` — API endpoint for the LLM
- `MODEL_NAME` — model identifier used for inference
- `HF_TOKEN` — Hugging Face / API key

If using a Docker-based environment creation flow, the implementation may also use:

- `IMAGE_NAME` or equivalent local image variable

### 12.7 Mandatory Inference Script Location

The inference script must:

- be named exactly `inference.py`
- be placed in the root directory of the project

### 12.8 Mandatory Client Requirement

All LLM calls in the baseline script must use the OpenAI Python client configured through:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

### 12.9 Mandatory Structured Stdout Logging

The inference script must emit structured stdout logs strictly using the required line types:

- `[START]`
- `[STEP]`
- `[END]`

Any deviation in:

- field names
- field ordering
- formatting

may result in incorrect or failed evaluation.

### 12.10 Infrastructure Restrictions

The solution must respect the following constraints:

- inference runtime should be less than 20 minutes
- the environment and inference must run on a machine with `vcpu=2`
- memory usage must fit within `8 GB`

### 12.11 Validator Requirement

The project should be tested using the pre-submission validation script before final submission.

---

## 13. Inference Script Specification

The baseline inference implementation must follow the sample submission pattern and be production-ready for automated evaluation.

### 13.1 File Name and Location

The script must be:

- `inference.py`
- located at the repository root

### 13.2 Required Environment Variables

The script must read:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

Optional image or benchmark variables may be used when needed for container startup, but the core script must rely on the required variables above for LLM access.

### 13.3 OpenAI Client Requirement

The script must use the OpenAI client for all model calls.

Example configuration pattern:

```python
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("API_BASE_URL"),
    api_key=os.getenv("HF_TOKEN"),
)
```

### 13.4 Logging Format

The script must emit exactly these three line types to stdout:

```text
[START] task=<task_name> env=<benchmark> model=<model_name>
[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> score=<0.000> rewards=<r1,r2,...,rn>
```

### 13.5 Logging Rules

- one `[START]` line at episode begin
- one `[STEP]` line immediately after each `env.step()` call
- one `[END]` line after environment close, even if an exception occurs
- `reward` must be formatted to 2 decimal places
- `rewards` values must be formatted to 2 decimal places
- `score` should be formatted consistently
- `done` and `success` must be lowercase booleans
- `error` must be the raw last-action error string or `null`
- each log record must be on a single line

### 13.6 Inference Script Behavioral Requirements

The script must:

- initialize the OpenAI client using the required environment variables
- initialize the environment
- call `reset()`
- repeatedly call the model to produce the next action
- execute `step(action)`
- log every step
- close the environment
- emit `[END]` unconditionally

### 13.7 Reproducibility Requirements

The script should use:

- fixed prompts
- fixed task ordering
- fixed step limits
- stable decoding parameters where possible

This is required to improve score reproducibility.

### 13.8 Runtime Constraints

The script should complete within 20 minutes under the target hardware constraints.

---

## 14. Pre-Validation Script Reference

The project should include or support execution of a pre-validation script equivalent to the provided validator.

### 14.1 Validator Purpose

The validator checks:

1. HF Space reachability and `/reset` response
2. Docker build success
3. `openenv validate` success

### 14.2 Validator Expectations

The repository should be structured so the validator can:

- locate the `Dockerfile` in the root or expected build directory
- run `docker build`
- run `openenv validate`
- ping the deployed Space URL

### 14.3 Recommended Local Validation Flow

Before submission, the implementer should verify:

1. `docker build` succeeds
2. `openenv validate` succeeds
3. `python inference.py` runs without errors
4. the deployed HF Space returns `200` from `/reset`

### 14.4 Suggested Repository Support

The repository should contain:

- `inference.py` in root
- `Dockerfile` in root
- `openenv.yaml` in root
- a clear README validation section
- optional `scripts/validate-submission.sh`

---

## 15. Documentation Reference

The final `README.md` must include:

- project motivation
- description of the real-world workflow
- environment architecture
- OpenEnv compliance notes
- observation space definition
- action space definition
- reward function overview
- task list with difficulty labels
- setup instructions
- local usage instructions
- validation instructions
- baseline inference usage
- baseline scores
- Docker instructions
- Hugging Face Spaces notes

---

## 16. Recommended Repository Structure

```text
openenv-subopt/
  README.md
  REFERENCE_DOCUMENT.md
  openenv.yaml
  Dockerfile
  requirements.txt
  app.py
  inference.py
  real_estate_pipeline/
    __init__.py
    env.py
    models.py
    tasks.py
    graders.py
    rewards.py
    fixtures/
      residential_buyer_qualification.json
      residential_missing_info_followup.json
      commercial_lease_strategy.json
  tests/
    test_env.py
    test_graders.py
  scripts/
    validate-submission.sh
```

---

## 17. Acceptance Criteria

The project shall be considered complete when:

- it simulates a real real-estate workflow
- it implements full OpenEnv models and methods
- it includes `openenv.yaml`
- it passes `openenv validate`
- it includes at least 3 graded tasks
- all graders return scores from `0.0` to `1.0`
- it uses dense rewards with partial progress
- it includes a reproducible OpenAI `inference.py` script in the project root
- the inference script uses `API_BASE_URL`, `MODEL_NAME`, and `HF_TOKEN`
- the inference script emits compliant `[START]`, `[STEP]`, and `[END]` logs
- it includes a working `Dockerfile`
- it is ready for Hugging Face Spaces deployment
- the HF Space responds to `/reset` with HTTP `200`
- the project fits the stated infrastructure constraints
- the pre-validation flow succeeds
- it includes a complete `README.md`

---

## 18. Implementation Notes For This Project

To align this project with the submission rules, the implementation should specifically include:

- a root-level `inference.py` instead of `baseline_inference.py`
- OpenAI client initialization using `HF_TOKEN`
- support for `API_BASE_URL` and `MODEL_NAME`
- strict stdout log helpers for `[START]`, `[STEP]`, and `[END]`
- task-by-task execution across the 3 required tasks
- safe environment closing in a `finally` block
- validation instructions for both local and deployed checks

---

## 19. Final Recommendation

This merged idea is a strong OpenEnv project because it is:

- realistic
- operationally meaningful
- commercially relevant
- multi-stage without being too broad
- structured enough for deterministic evaluation

It is recommended as the final reference concept for implementation.
