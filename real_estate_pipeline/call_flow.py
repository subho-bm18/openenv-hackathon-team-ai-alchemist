from __future__ import annotations

from typing import Any

from .models import CallTurn


def build_call_script(opportunity: dict[str, Any], purpose: str | None = None) -> tuple[list[CallTurn], str]:
    segment = opportunity.get("segment")
    customer_name = opportunity.get("customer_name", "Customer")
    location = opportunity.get("location", "the target area")
    profession = opportunity.get("profession", "customer")
    employment_type = opportunity.get("employment_type", "working profile")
    total_experience = opportunity.get("total_experience_years")
    experience_text = f" with {total_experience} years of experience" if total_experience is not None else ""

    if segment == "commercial":
        business_type = opportunity.get("business_type", "business")
        transcript = [
            CallTurn(speaker="agent", text=f"Hi {customer_name}, this is the leasing desk calling to discuss your {business_type} requirement in {location}."),
            CallTurn(speaker="customer", text=f"Yes, we are interested. I run this as a {employment_type} {business_type}{experience_text}, so the location, frontage, and commercials all matter."),
            CallTurn(speaker="agent", text="We have a relevant option and I want to confirm budget comfort, handover timing, operating profile, and your availability for a landlord meeting."),
            CallTurn(speaker="customer", text="That works. We can move quickly if the meeting and commercial structure make sense."),
            CallTurn(speaker="agent", text=purpose or "Great, I will coordinate the landlord discussion and keep the negotiation moving."),
        ]
        return transcript, "customer_confirmed_for_commercial_followup"

    property_type = opportunity.get("property_type", "property")
    transcript = [
        CallTurn(speaker="agent", text=f"Hi {customer_name}, this is the sales desk calling about your {property_type} requirement in {location}."),
        CallTurn(speaker="customer", text=f"Yes, I am actively looking. I work as a {profession} on a {employment_type} basis{experience_text} and can visit if the property is a good fit."),
        CallTurn(speaker="agent", text="I want to confirm your move timeline, work profile, interest in the shortlisted option, and whether you want cab support for the site visit."),
        CallTurn(speaker="customer", text="The timeline still works for me. Please go ahead with the next step, and yes, I would like pickup and drop if the builder approves it."),
        CallTurn(speaker="agent", text=purpose or "Perfect, I will schedule the builder-side appointment and share the details with you."),
    ]
    return transcript, "customer_confirmed_for_site_visit"


def summarize_call(transcript: list[CallTurn]) -> str:
    if not transcript:
        return "No call transcript available."
    customer_lines = [turn.text for turn in transcript if turn.speaker == "customer"]
    if not customer_lines:
        return transcript[-1].text
    return customer_lines[-1]
