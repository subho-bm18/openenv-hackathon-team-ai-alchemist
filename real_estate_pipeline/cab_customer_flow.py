from __future__ import annotations

from typing import Any

from .models import NotificationMessage


def evaluate_cab_eligibility(opportunity: dict[str, Any], property_record: dict[str, Any] | None) -> dict[str, Any]:
    builder_cab_available = bool((property_record or {}).get("details", {}).get("builder_cab_available"))
    pickup_location = opportunity.get("customer_location") or opportunity.get("location")
    drop_location = (property_record or {}).get("location")

    pickup_eligible = bool(pickup_location)
    drop_eligible = bool(drop_location)
    builder_approved = builder_cab_available and pickup_eligible and drop_eligible
    eligibility_status = "eligible" if builder_approved else "not_eligible"

    if builder_approved:
        customer_response = (
            f"Pickup from {pickup_location} and drop to {drop_location} are eligible under the builder cab program. "
            "We can proceed with the booking now."
        )
    elif not builder_cab_available:
        customer_response = (
            "The builder has not approved complimentary cab support for this property, so pickup and drop cannot be offered."
        )
    elif not pickup_eligible and not drop_eligible:
        customer_response = "Neither pickup nor drop is currently eligible because the source and destination details are incomplete."
    elif not pickup_eligible:
        customer_response = "Cab support cannot be confirmed yet because the pickup location is missing or outside the eligible service area."
    else:
        customer_response = "Cab support cannot be confirmed yet because the drop location is missing or not serviceable for this property."

    return {
        "builder_provides_cab": builder_cab_available,
        "builder_cab_approved": builder_approved,
        "pickup_eligible": pickup_eligible,
        "drop_eligible": drop_eligible,
        "cab_eligibility_status": eligibility_status,
        "cab_customer_response": customer_response,
        "pickup_location": pickup_location,
        "drop_location": drop_location,
    }


def build_cab_notifications(opportunity: dict[str, Any]) -> list[NotificationMessage]:
    customer_name = opportunity.get("customer_name", "Customer")
    booking_reference = opportunity.get("cab_booking_reference", "pending-reference")
    pickup_location = opportunity.get("cab_pickup_location", "your pickup point")
    drop_location = opportunity.get("cab_drop_location", "the property")
    provider = (opportunity.get("cab_booking_provider") or "cab partner").title()

    message = (
        f"Hi {customer_name}, your site-visit cab is confirmed with {provider}. "
        f"Pickup: {pickup_location}. Drop: {drop_location}. "
        f"Booking reference: {booking_reference}."
    )
    return [
        NotificationMessage(channel="chat", recipient=customer_name, message=message),
        NotificationMessage(channel="sms", recipient=customer_name, message=message),
        NotificationMessage(channel="whatsapp", recipient=customer_name, message=message),
    ]
