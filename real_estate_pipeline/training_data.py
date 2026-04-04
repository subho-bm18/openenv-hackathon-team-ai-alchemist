from __future__ import annotations

from copy import deepcopy
from itertools import islice
from typing import Any, Iterable

from .env import RealEstatePipelineEnv
from .live_simulator import DEFAULT_INVENTORY, LiveTrafficAgent, build_runtime_task
from .models import InboundLead
from .tasks import list_eval_task_ids, list_task_ids, load_eval_task, load_task


def build_training_records() -> list[dict[str, Any]]:
    return build_task_training_records()


def build_task_training_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for task in iter_all_tasks():
        records.append(_task_record(task["task"], source=task["source"]))

    return records


def build_step_training_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for task_entry in iter_all_tasks():
        records.extend(_step_records(task_entry["task"], source=task_entry["source"]))

    return records


def iter_all_tasks() -> Iterable[dict[str, Any]]:
    for task_id in list_task_ids():
        yield {"source": "fixture", "task": load_task(task_id)}

    for task_id in list_eval_task_ids():
        yield {"source": "eval_fixture", "task": load_eval_task(task_id)}

    for lead in generate_synthetic_leads():
        yield {"source": "simulated_live", "task": build_runtime_task(lead)}


def generate_synthetic_leads() -> list[InboundLead]:
    residential_names = [
        "Aarav Mehta",
        "Priya Nair",
        "Rohan Kapoor",
        "Sneha Iyer",
        "Vikram Shah",
        "Ananya Rao",
    ]
    residential_locations = ["Whitefield", "Sarjapur", "West Side", "Hebbal", "Electronic City", "Indiranagar"]
    residential_property_types = ["2BHK apartment", "3BHK apartment", "3-bedroom home"]
    residential_budgets = [7800000, 9500000, 11000000, 14500000]
    residential_timelines = [15, 30, 45]
    residential_missing_sets = [
        [],
        ["budget"],
        ["timeline_days"],
        ["budget", "timeline_days", "financing_status"],
    ]

    residential_leads: list[InboundLead] = []
    residential_counter = 1
    for name in residential_names:
        for location in residential_locations:
            for property_type in residential_property_types:
                budget = residential_budgets[residential_counter % len(residential_budgets)]
                timeline = residential_timelines[residential_counter % len(residential_timelines)]
                missing_fields = residential_missing_sets[residential_counter % len(residential_missing_sets)]
                residential_leads.append(
                    InboundLead(
                        lead_id=f"synthetic_res_{residential_counter:03d}",
                        customer_name=name,
                        inquiry=_residential_inquiry(property_type, location, budget, timeline, missing_fields),
                        segment="residential",
                        budget=None if "budget" in missing_fields else budget,
                        location=location,
                        timeline_days=None if "timeline_days" in missing_fields else timeline,
                        property_type=property_type,
                        missing_fields=missing_fields,
                    )
                )
                residential_counter += 1

    commercial_names = ["Northline Retail", "Bean Street Cafe", "Urban Basket", "Axis Workspace"]
    commercial_locations = ["CBD Retail District", "Secondary Business Park", "Airport Corridor"]
    business_types = ["cafe", "office", "retail"]
    budgets = [240000, 290000, 320000, 360000]
    timelines = [30, 45, 60]
    sqft_ranges = [(1800, 2200), (2200, 2800), (2600, 3200)]

    commercial_leads: list[InboundLead] = []
    commercial_counter = 1
    for name in commercial_names:
        for location in commercial_locations:
            for business_type in business_types:
                budget = budgets[commercial_counter % len(budgets)]
                timeline = timelines[commercial_counter % len(timelines)]
                sqft_min, sqft_max = sqft_ranges[commercial_counter % len(sqft_ranges)]
                commercial_leads.append(
                    InboundLead(
                        lead_id=f"synthetic_com_{commercial_counter:03d}",
                        customer_name=name,
                        inquiry=_commercial_inquiry(business_type, location, budget, timeline, sqft_min, sqft_max),
                        segment="commercial",
                        budget=budget,
                        location=location,
                        timeline_days=timeline,
                        business_type=business_type,
                        square_feet_min=sqft_min,
                        square_feet_max=sqft_max,
                    )
                )
                commercial_counter += 1

    all_leads = residential_leads + commercial_leads
    return list(islice(all_leads, 120))


def _task_record(task: dict[str, Any], source: str) -> dict[str, Any]:
    opportunity = deepcopy(task["opportunity"])
    return {
        "record_type": "task",
        "source": source,
        "task_id": task["task_id"],
        "input": {
            "inquiry": opportunity.get("inquiry"),
            "segment": opportunity.get("segment"),
            "lead_profile": {
                "budget": opportunity.get("budget"),
                "location": opportunity.get("location"),
                "timeline_days": opportunity.get("timeline_days"),
                "property_type": opportunity.get("property_type"),
                "business_type": opportunity.get("business_type"),
                "square_feet_min": opportunity.get("square_feet_min"),
                "square_feet_max": opportunity.get("square_feet_max"),
                "missing_fields": opportunity.get("missing_fields", []),
            },
            "inventory": deepcopy(task["inventory"]),
            "business_rules": deepcopy(task["business_rules"]),
        },
        "target": {
            "category": task["expected"].get("category"),
            "priority": task["expected"].get("priority"),
            "requested_fields": task["expected"].get("requested_fields", []),
            "property_id": task["expected"].get("property_id"),
            "lease_terms": deepcopy(task["expected"].get("lease_terms")),
            "stage": task["expected"].get("stage"),
        },
    }


def _step_records(task: dict[str, Any], source: str) -> list[dict[str, Any]]:
    env = RealEstatePipelineEnv(max_steps=8)
    agent = LiveTrafficAgent()
    observation = env.reset_runtime(task)
    records: list[dict[str, Any]] = []

    for step in range(1, env.max_steps + 1):
        thought, action = agent.choose_action(observation)
        records.append(
            {
                "record_type": "step",
                "source": source,
                "task_id": task["task_id"],
                "step": step,
                "input": {
                    "observation": observation.model_dump(),
                    "inquiry": observation.active_opportunity.inquiry,
                    "segment": observation.active_opportunity.segment,
                },
                "target": {
                    "action_type": action.action_type,
                    "action_payload": action.model_dump(exclude_none=True),
                    "category": task["expected"].get("category"),
                    "priority": task["expected"].get("priority"),
                    "stage": task["expected"].get("stage"),
                },
                "metadata": {
                    "thought": thought,
                },
            }
        )
        result = env.step(action)
        observation = result.observation
        if result.done:
            break

    return records


def _residential_inquiry(
    property_type: str,
    location: str,
    budget: int,
    timeline_days: int,
    missing_fields: list[str],
) -> str:
    parts = [f"Looking for a {property_type} in {location}."]
    if "budget" not in missing_fields:
        parts.append(f"My budget is around {budget // 100000} lakhs.")
    if "timeline_days" not in missing_fields:
        parts.append(f"I want to close within {timeline_days} days.")
    if "financing_status" in missing_fields:
        parts.append("Still finalizing the financing plan.")
    return " ".join(parts)


def _commercial_inquiry(
    business_type: str,
    location: str,
    budget: int,
    timeline_days: int,
    square_feet_min: int,
    square_feet_max: int,
) -> str:
    return (
        f"We need {square_feet_min} to {square_feet_max} square feet for a {business_type} in {location}. "
        f"Our opening target is in {timeline_days} days and we can spend up to {budget} monthly for the right fit."
    )
