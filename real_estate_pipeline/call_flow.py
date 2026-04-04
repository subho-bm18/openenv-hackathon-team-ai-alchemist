from __future__ import annotations

from typing import Any

from .models import CallTurn


def build_call_script(opportunity: dict[str, Any], purpose: str | None = None) -> tuple[list[CallTurn], str]:
    segment = opportunity.get("segment")
    customer_name = opportunity.get("customer_name", "Customer")
    location = opportunity.get("location", "the target area")
    inquiry = opportunity.get("inquiry", "")

    if segment == "commercial":
        business_type = opportunity.get("business_type", "business")
        transcript = [
            CallTurn(speaker="agent", text=f"Hi {customer_name}, this is the leasing desk calling to discuss your {business_type} requirement in {location}."),
            CallTurn(speaker="customer", text="Yes, we are interested if the location, frontage, and commercials line up."),
            CallTurn(speaker="agent", text="We have a relevant option and I want to confirm budget comfort, handover timing, and your availability for a landlord meeting."),
            CallTurn(speaker="customer", text="That works. We can move quickly if the meeting and commercial structure make sense."),
            CallTurn(speaker="agent", text=purpose or "Great, I will coordinate the landlord discussion and keep the negotiation moving."),
        ]
        return transcript, "customer_confirmed_for_commercial_followup"

    property_type = opportunity.get("property_type", "property")
    transcript = [
        CallTurn(speaker="agent", text=f"Hi {customer_name}, this is the sales desk calling about your {property_type} requirement in {location}."),
        CallTurn(speaker="customer", text="Yes, I am actively looking and can visit if the property is a good fit."),
        CallTurn(speaker="agent", text="I want to confirm your move timeline and interest in the shortlisted option before I coordinate the next appointment."),
        CallTurn(speaker="customer", text="The timeline still works for me. Please go ahead with the next step."),
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
