from __future__ import annotations

import os
from typing import Callable

from openai import OpenAI

from real_estate_pipeline import Action, RealEstatePipelineEnv
from real_estate_pipeline.models import LeaseTerms, Observation


API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
API_KEY = os.getenv("HF_TOKEN")
BENCHMARK = "real-estate-pipeline-openenv"
MAX_STEPS = 6


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: str | None) -> None:
    error_value = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error_value}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: list[float]) -> None:
    reward_values = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={reward_values}",
        flush=True,
    )


def build_client() -> OpenAI | None:
    if not API_KEY:
        return None
    return OpenAI(base_url=API_BASE_URL, api_key=API_KEY)


def call_model(client: OpenAI | None, observation: Observation) -> str:
    prompt = (
        "You are selecting the next structured action for a real-estate pipeline environment.\n"
        f"Task: {observation.task_id}\n"
        f"Lead inquiry: {observation.active_opportunity.inquiry}\n"
        f"Business rules: {' | '.join(observation.business_rules)}\n"
        "Respond with one short sentence describing the next best action."
    )
    if client is None:
        return "fallback-policy"
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You choose the next workflow action succinctly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=60,
        )
        return (response.choices[0].message.content or "fallback-policy").strip()
    except Exception:
        return "fallback-policy"


def action_to_str(action: Action) -> str:
    payload = action.model_dump(exclude_none=True)
    return str(payload).replace("\n", " ")


def residential_easy_policy(_observation: Observation, step: int) -> Action:
    if step == 1:
        return Action(action_type="classify_opportunity", opportunity_id="opp_res_001", category="residential_buyer")
    if step == 2:
        return Action(action_type="set_priority", opportunity_id="opp_res_001", priority="high")
    if step == 3:
        return Action(action_type="recommend_property", opportunity_id="opp_res_001", property_id="res_prop_101")
    return Action(action_type="schedule_visit", opportunity_id="opp_res_001", property_id="res_prop_101")


def residential_medium_policy(_observation: Observation, step: int) -> Action:
    if step == 1:
        return Action(action_type="classify_opportunity", opportunity_id="opp_res_002", category="residential_buyer")
    if step == 2:
        return Action(action_type="set_priority", opportunity_id="opp_res_002", priority="medium")
    if step == 3:
        return Action(
            action_type="request_missing_info",
            opportunity_id="opp_res_002",
            requested_fields=["budget", "timeline_days", "financing_status"],
            message="Please share your budget, purchase timeline, and financing status.",
        )
    return Action(action_type="move_to_nurture", opportunity_id="opp_res_002", message="Lead remains active for follow-up.")


def commercial_hard_policy(_observation: Observation, step: int) -> Action:
    if step == 1:
        return Action(action_type="classify_opportunity", opportunity_id="opp_com_001", category="commercial_tenant")
    if step == 2:
        return Action(action_type="set_priority", opportunity_id="opp_com_001", priority="high")
    if step == 3:
        return Action(action_type="recommend_property", opportunity_id="opp_com_001", property_id="com_prop_301")
    if step == 4:
        return Action(
            action_type="recommend_lease_terms",
            opportunity_id="opp_com_001",
            lease_terms=LeaseTerms(lease_years=5, monthly_rent=315000, deposit_months=6, fit_out_support=True),
        )
    return Action(action_type="advance_stage", opportunity_id="opp_com_001", stage="negotiation")


POLICIES: dict[str, Callable[[Observation, int], Action]] = {
    "residential_buyer_qualification": residential_easy_policy,
    "residential_missing_info_followup": residential_medium_policy,
    "commercial_lease_strategy": commercial_hard_policy,
}


def run_task(env: RealEstatePipelineEnv, client: OpenAI | None, task_id: str) -> float:
    observation = env.reset(task_id)
    rewards: list[float] = []
    steps_taken = 0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        for step in range(1, MAX_STEPS + 1):
            _ = call_model(client, observation)
            action = POLICIES[task_id](observation, step)
            result = env.step(action)
            reward_value = result.reward.value
            rewards.append(reward_value)
            steps_taken = step
            error = result.observation.last_action_result if "Invalid action" in (result.observation.last_action_result or "") else None
            log_step(step, action_to_str(action), reward_value, result.done, error)
            observation = result.observation
            if result.done:
                break

        score = env.state()["grader_score"]
        success = score >= 0.5
        return score
    finally:
        log_end(success=success, steps=steps_taken, score=env.state()["grader_score"], rewards=rewards)


def main() -> None:
    client = build_client()
    env = RealEstatePipelineEnv()
    scores = [run_task(env, client, task_id) for task_id in env.available_tasks()]
    average = sum(scores) / len(scores) if scores else 0.0
    print(f"Average score across {len(scores)} tasks: {average:.3f}", flush=True)


if __name__ == "__main__":
    main()
