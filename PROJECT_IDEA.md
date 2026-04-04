# OpenEnv Project Idea: Customer Support Inbox Simulator

## 1. Recommended Project

Build an OpenEnv environment that simulates a **customer support specialist** handling an inbox of support tickets for a SaaS company.

This is a strong fit for your requirements because:

- It is a real-world task that humans actually do every day.
- It supports structured observations and actions.
- It naturally allows multiple difficulty levels.
- It has deterministic grading criteria.
- It supports dense rewards through partial progress.
- It is easy to explain and demo in a Hugging Face Space.

---

## 2. Environment Concept

### Name
`support-inbox-openenv`

### Real-world scenario
An agent plays the role of a support operations associate for a fictional SaaS product. The inbox contains customer emails or ticket threads. The agent must:

- read ticket details
- classify urgency and issue type
- gather missing information
- draft safe and policy-compliant replies
- escalate tickets when needed
- resolve tickets when enough information is available

This is not a game. It simulates an actual support workflow used in software companies.

---

## 3. Why This Idea Is Good For OpenEnv

### Typed models
You can cleanly define:

- `Observation`: ticket queue, current ticket, conversation history, policy snippets, allowed actions
- `Action`: open ticket, tag ticket, request info, escalate, draft reply, resolve
- `Reward`: step reward, progress signals, penalties, final score

### Full OpenEnv interface
You can implement:

- `reset()` to load a fresh support scenario
- `step(action)` to update the queue and return reward/progress
- `state()` to expose internal state for debugging and evaluation
- `openenv.yaml` for metadata and validation

### Good reward shaping
The environment can reward:

- selecting the correct ticket
- applying the correct label
- identifying missing information
- escalating security/billing issues correctly
- drafting a response with required facts

And penalize:

- resolving too early
- unsafe responses
- wrong escalation
- repetitive no-op behavior
- wasting too many steps

---

## 4. Proposed Tasks

You need at least 3 tasks with agent graders. Here is a clean progression:

### Task 1: Easy
**Title:** Password Reset Triage

**Scenario:**
A customer cannot log in and requests a password reset. The ticket contains enough information to respond safely.

**Expected agent behavior:**

- open the ticket
- classify it as `account_access`
- set priority to `normal`
- send the correct reset guidance
- mark it resolved

**Deterministic grading example:**

- `0.25` if correct category applied
- `0.25` if correct priority applied
- `0.25` if reply includes required reset instructions
- `0.25` if ticket is resolved correctly

### Task 2: Medium
**Title:** Refund Request With Missing Information

**Scenario:**
A customer asks for a refund but does not include the order ID required by policy.

**Expected agent behavior:**

- classify as `billing_refund`
- identify missing order information
- request the missing order ID before resolution
- avoid falsely approving the refund

**Deterministic grading example:**

- `0.20` if correct category
- `0.20` if correct priority
- `0.30` if reply asks for the missing required field
- `0.20` if ticket remains open
- `0.10` if tone is compliant and non-committal

### Task 3: Hard
**Title:** Possible Account Compromise Escalation

**Scenario:**
A customer reports suspicious login activity, changed email settings, and possible unauthorized access.

**Expected agent behavior:**

- classify as `security_incident`
- set priority to `high` or `urgent`
- avoid sharing unsafe recovery instructions publicly
- escalate to the security team
- communicate next steps clearly

**Deterministic grading example:**

- `0.20` if correct category
- `0.20` if correct urgency
- `0.30` if escalated to the correct team
- `0.20` if reply includes approved safety language
- `0.10` if not incorrectly resolved

---

## 5. Action Space

Your README should define an action space similar to this:

### Example actions

- `open_ticket(ticket_id)`
- `set_category(ticket_id, category)`
- `set_priority(ticket_id, priority)`
- `request_information(ticket_id, fields, message)`
- `draft_reply(ticket_id, message)`
- `escalate_ticket(ticket_id, team, reason)`
- `resolve_ticket(ticket_id, resolution_code)`
- `close_without_action(ticket_id, reason)`

### Why this is good

- It is realistic.
- It is structured and easy to validate.
- It reduces ambiguity for graders.
- It supports partial progress rewards.

---

## 6. Observation Space

### Example observation fields

- queue summary
- active ticket id
- customer message history
- account metadata
- allowed policy snippets
- prior actions taken
- remaining step budget

### Example `Observation` model fields

- `task_id: str`
- `step_count: int`
- `remaining_steps: int`
- `queue: list[TicketSummary]`
- `active_ticket: TicketDetail | None`
- `policy_context: list[str]`
- `available_actions: list[str]`
- `last_action_result: str | None`

---

## 7. Reward Design

Use a dense reward rather than a binary-only score.

### Example reward signals

- `+0.10` for opening the correct ticket first
- `+0.15` for correct category
- `+0.10` for correct priority
- `+0.20` for asking for required missing information
- `+0.25` for correct escalation
- `+0.20` for correct final resolution
- `-0.10` for invalid actions
- `-0.10` for repeated unnecessary actions
- `-0.20` for unsafe resolution
- `-0.02` small step penalty to discourage loops

### Why this matters

This gives meaningful learning signal over the whole trajectory and satisfies the requirement for partial progress rewards.

---

## 8. Agent Graders

Each task should have a deterministic grader function, for example:

- `grade_easy_password_reset(final_state) -> float`
- `grade_medium_refund_missing_info(final_state) -> float`
- `grade_hard_security_escalation(final_state) -> float`

### Grader inputs

- final ticket state
- action history
- final reply content
- tags, priority, escalation target, resolution status

### Grader properties

- deterministic
- returns score from `0.0` to `1.0`
- based on explicit rules
- easy to reproduce

---

## 9. OpenEnv Spec Checklist

Your implementation should include all of the following:

- typed Pydantic models for `Observation`, `Action`, `Reward`
- environment class implementing:
  - `reset()`
  - `step(action)`
  - `state()`
- `openenv.yaml`
- validation support via `openenv validate`
- at least 3 tasks
- task graders with scores `0.0` to `1.0`
- baseline inference script using `OPENAI_API_KEY`
- reproducible evaluation output
- `Dockerfile`
- Hugging Face Spaces deployment config
- README with setup and baseline scores

---

## 10. Suggested Repo Structure

```text
openenv-subopt/
  README.md
  openenv.yaml
  Dockerfile
  requirements.txt
  app.py
  baseline_inference.py
  support_inbox/
    __init__.py
    env.py
    models.py
    tasks.py
    graders.py
    rewards.py
    policies.py
    fixtures/
      easy_password_reset.json
      medium_refund_missing_info.json
      hard_security_incident.json
  tests/
    test_env.py
    test_graders.py
```

---

## 11. README Sections You Will Need

Your final `README.md` should include:

- project overview and motivation
- why the task is real-world
- environment description
- observation space definition
- action space definition
- reward design
- task descriptions
- difficulty progression
- setup instructions
- local run instructions
- validation instructions
- baseline inference instructions
- baseline scores for all 3 tasks
- Docker usage
- Hugging Face Spaces deployment notes

---

## 12. Baseline Inference Script Idea

Create a script like `baseline_inference.py` that:

- loads all 3 tasks
- runs a selected OpenAI model using `OPENAI_API_KEY`
- interacts with the environment step by step
- logs action traces
- prints per-task score and overall average

### Example output

```text
Task easy_password_reset: 1.00
Task medium_refund_missing_info: 0.80
Task hard_security_incident: 0.65
Average score: 0.82
```

For reproducibility:

- use fixed task fixtures
- use fixed prompts
- use fixed model name
- use deterministic settings when available

---

## 13. Hugging Face Space Plan

Use a Docker-based Space with tag `openenv`.

### Minimal app behavior

The Space can:

- describe the environment
- let users run a demo task
- show current observation and reward
- optionally run the baseline agent

### Files needed

- `Dockerfile`
- simple `app.py` or Gradio app
- `requirements.txt`

---

## 14. Why This Is Better Than Other Ideas

This support inbox simulator is better than many other ideas because:

- simpler than code review but still realistic
- easier to make deterministic than customer chat
- more convincing than a toy workflow
- supports rich intermediate rewards
- easy to explain to judges and reviewers

---

## 15. Alternative Real-world Ideas

If you want backups, these are also strong:

### Option A
**Email Triage Assistant**

- classify inbound emails
- draft responses
- escalate sensitive cases

### Option B
**Data Cleaning Analyst**

- inspect tabular records
- detect duplicates
- repair missing values
- mark anomalies

### Option C
**Meeting Scheduler**

- compare calendars
- resolve conflicts
- send scheduling proposals

Out of these, **Customer Support Inbox Simulator** is the easiest to turn into a polished OpenEnv submission quickly.

---

## 16. Recommended Next Step

Recommended project to build:

**Customer Support Inbox Simulator for a SaaS company**

If you want, the next step can be:

1. I create the full project scaffold.
2. I implement the OpenEnv models and environment.
3. I add the 3 tasks, graders, Dockerfile, and README.

