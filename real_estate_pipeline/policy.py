from __future__ import annotations

from typing import Any

from .models import LeaseTerms, PropertyRecord


def choose_category(opportunity: Any) -> str:
    return "commercial_tenant" if value_of(opportunity, "segment") == "commercial" else "residential_buyer"


def lead_readiness_score(opportunity: Any) -> float:
    score = 0.0
    if value_of(opportunity, "budget"):
        score += 0.3
    if value_of(opportunity, "timeline_days"):
        score += 0.2
    if value_of(opportunity, "location"):
        score += 0.2
    if value_of(opportunity, "property_type") or value_of(opportunity, "business_type"):
        score += 0.2

    missing_fields = value_of(opportunity, "missing_fields") or []
    score -= min(len(missing_fields) * 0.1, 0.3)
    return max(0.0, min(1.0, round(score, 4)))


def choose_priority(opportunity: Any) -> str:
    readiness = lead_readiness_score(opportunity)
    timeline_days = value_of(opportunity, "timeline_days")
    if readiness >= 0.75 and timeline_days and timeline_days <= 45:
        return "high"
    if readiness >= 0.45:
        return "medium"
    return "low"


def property_fit_score(opportunity: Any, property_record: PropertyRecord | dict[str, Any]) -> float:
    segment = value_of(opportunity, "segment")
    if value_of(property_record, "segment") != segment:
        return 0.0

    score = 0.0
    max_score = 10.0

    location = value_of(opportunity, "location")
    if location and value_of(property_record, "location") == location:
        score += 3.0

    budget = value_of(opportunity, "budget")
    price = value_of(property_record, "price") or 0
    if budget:
        if price <= budget:
            score += 3.0
        elif price <= budget * 1.1:
            score += 1.5

    property_type = value_of(opportunity, "property_type")
    details = value_of(property_record, "details") or {}
    if property_type and details.get("property_type") == property_type:
        score += 2.0

    square_feet_min = value_of(opportunity, "square_feet_min")
    square_feet_max = value_of(opportunity, "square_feet_max")
    sqft = details.get("square_feet", 0)
    if square_feet_min and sqft >= square_feet_min:
        score += 1.0
    if square_feet_max and sqft and sqft <= square_feet_max:
        score += 1.0

    business_type = value_of(opportunity, "business_type")
    if business_type == "cafe" and details.get("fit_for") == "retail_food":
        score += 1.0

    return max(0.0, min(1.0, round(score / max_score, 4)))


def best_property_match(opportunity: Any, inventory: list[PropertyRecord]) -> PropertyRecord | None:
    ranked: list[tuple[float, PropertyRecord]] = []
    for property_record in inventory:
        fit = property_fit_score(opportunity, property_record)
        if fit > 0:
            ranked.append((fit, property_record))

    if not ranked:
        return None

    ranked.sort(key=lambda item: (item[0], -item[1].price), reverse=True)
    return ranked[0][1]


def recommended_lease_terms(opportunity: Any, inventory: list[PropertyRecord]) -> LeaseTerms:
    matched_property = best_property_match(opportunity, inventory)
    budget = value_of(opportunity, "budget") or 0
    monthly_rent = min(budget, matched_property.price) if matched_property and budget else (matched_property.price if matched_property else budget)
    return LeaseTerms(
        lease_years=5,
        monthly_rent=monthly_rent or None,
        deposit_months=6,
        fit_out_support=True,
    )


def priority_alignment_score(actual_priority: str | None, expected_priority: str | None) -> float:
    if not actual_priority or not expected_priority:
        return 0.0
    if actual_priority == expected_priority:
        return 1.0

    ordered = ["low", "medium", "high"]
    if actual_priority not in ordered or expected_priority not in ordered:
        return 0.0

    distance = abs(ordered.index(actual_priority) - ordered.index(expected_priority))
    if distance == 1:
        return 0.5
    return 0.0


def stage_alignment_score(actual_stage: str | None, expected_stage: str | None) -> float:
    if not actual_stage or not expected_stage:
        return 0.0
    if actual_stage == expected_stage:
        return 1.0

    compatible_stages = {
        "visit_scheduled": {"new"},
        "builder_appointment_scheduled": {"visit_scheduled", "new"},
        "landlord_meeting_scheduled": {"negotiation", "proposal_shared"},
        "deal_closed": {"negotiation", "landlord_meeting_scheduled"},
        "nurture": {"awaiting_customer"},
        "negotiation": {"qualified", "proposal_shared"},
    }
    if actual_stage in compatible_stages.get(expected_stage, set()):
        return 0.5
    return 0.0


def lease_terms_alignment_score(actual: dict[str, Any], expected: dict[str, Any]) -> float:
    if not actual or not expected:
        return 0.0

    score = 0.0
    if actual.get("lease_years") == expected.get("lease_years"):
        score += 0.3
    if actual.get("deposit_months") == expected.get("deposit_months"):
        score += 0.2
    if bool(actual.get("fit_out_support")) == bool(expected.get("fit_out_support")):
        score += 0.2

    actual_rent = int(actual.get("monthly_rent", 0))
    expected_rent = int(expected.get("monthly_rent", 0))
    if expected_rent > 0:
        variance = abs(actual_rent - expected_rent) / expected_rent
        if variance <= 0.02:
            score += 0.3
        elif variance <= 0.05:
            score += 0.2
        elif variance <= 0.1:
            score += 0.1

    return max(0.0, min(1.0, round(score, 4)))


def value_of(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)
