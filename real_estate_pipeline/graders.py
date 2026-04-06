from __future__ import annotations

from typing import Any

from .policy import (
    lease_terms_alignment_score,
    priority_alignment_score,
    property_fit_score,
    stage_alignment_score,
)


def _clip(score: float) -> float:
    return max(0.0, min(1.0, round(score, 4)))


def grade_task(task: dict[str, Any], state: dict[str, Any]) -> float:
    opportunity = state["active_opportunity"]
    expected = task["expected"]
    score = 0.0

    if opportunity.get("category") == expected.get("category"):
        score += expected["weights"].get("category", 0.0)

    score += expected["weights"].get("priority", 0.0) * priority_alignment_score(
        opportunity.get("priority"),
        expected.get("priority"),
    )

    score += _property_match_component(task, state)
    if "customer_contact" in expected.get("weights", {}):
        score += expected["weights"].get("customer_contact", 0.0) * _contact_alignment_score(
            opportunity.get("customer_contacted"),
            expected.get("customer_contacted"),
        )
    if "visit_interest" in expected.get("weights", {}):
        score += expected["weights"].get("visit_interest", 0.0) * _boolean_alignment_score(
            opportunity.get("interested_in_visit"),
            expected.get("interested_in_visit"),
        )
    if "builder_cab" in expected.get("weights", {}):
        score += expected["weights"].get("builder_cab", 0.0) * _boolean_alignment_score(
            opportunity.get("builder_provides_cab"),
            expected.get("builder_provides_cab"),
        )
    if "cab_booking" in expected.get("weights", {}):
        score += expected["weights"].get("cab_booking", 0.0) * _status_alignment_score(
            opportunity.get("cab_booking_status"),
            expected.get("cab_booking_status"),
        )
    if "proposal_sent" in expected.get("weights", {}):
        score += expected["weights"].get("proposal_sent", 0.0) * _boolean_alignment_score(
            opportunity.get("proposal_sent"),
            expected.get("proposal_sent"),
        )
    if "deal_closed" in expected.get("weights", {}):
        score += expected["weights"].get("deal_closed", 0.0) * _boolean_alignment_score(
            opportunity.get("deal_closed"),
            expected.get("deal_closed"),
        )

    if expected.get("requested_fields"):
        asked = set(state.get("requested_fields", []))
        needed = set(expected.get("requested_fields", []))
        if needed:
            score += expected["weights"].get("missing_info", 0.0) * (len(asked & needed) / len(needed))
        score += expected["weights"].get("stage", 0.0) * stage_alignment_score(
            opportunity.get("stage"),
            expected.get("stage"),
        )

    elif expected.get("lease_terms"):
        terms = opportunity.get("lease_terms") or {}
        expected_terms = expected.get("lease_terms", {})
        score += expected["weights"].get("lease_terms", 0.0) * lease_terms_alignment_score(terms, expected_terms)
        score += expected["weights"].get("stage", 0.0) * stage_alignment_score(
            opportunity.get("stage"),
            expected.get("stage"),
        )

    else:
        score += expected["weights"].get("stage", 0.0) * stage_alignment_score(
            opportunity.get("stage"),
            expected.get("stage"),
        )

    return _clip(score)


def _property_match_component(task: dict[str, Any], state: dict[str, Any]) -> float:
    expected = task["expected"]
    weight = expected["weights"].get("property_match", 0.0)
    if not weight:
        return 0.0

    opportunity = state["active_opportunity"]
    recommended_id = opportunity.get("recommended_property_id")
    expected_id = expected.get("property_id")
    if not recommended_id or not expected_id:
        return 0.0
    if recommended_id == expected_id:
        return weight

    inventory = state.get("inventory_snapshot", [])
    candidate = next((item for item in inventory if item.get("property_id") == recommended_id), None)
    if candidate is None:
        return 0.0

    return weight * property_fit_score(opportunity, candidate)


def _contact_alignment_score(actual_contacted: bool | None, expected_contacted: bool | None) -> float:
    if expected_contacted is None:
        return 0.0
    return 1.0 if bool(actual_contacted) == bool(expected_contacted) else 0.0


def _boolean_alignment_score(actual: bool | None, expected: bool | None) -> float:
    if expected is None:
        return 0.0
    return 1.0 if bool(actual) == bool(expected) else 0.0


def _status_alignment_score(actual: str | None, expected: str | None) -> float:
    if expected is None:
        return 0.0
    return 1.0 if actual == expected else 0.0
