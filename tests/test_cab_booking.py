import os

from app import cab_booking_preview, cab_providers, create_cab_booking
from real_estate_pipeline.cab_booking import book_cab, preview_cab_booking


def test_cab_providers_expose_verified_provider_catalog() -> None:
    response = cab_providers()
    providers = {item["provider"]: item for item in response["providers"]}

    assert set(providers) == {"ola", "rapido", "uber"}
    assert providers["uber"]["supports_public_deeplink"] is True
    assert providers["ola"]["supports_partner_api"] is True
    assert providers["rapido"]["supports_partner_api"] is True


def test_uber_preview_returns_deeplink_when_client_id_present() -> None:
    previous = os.environ.get("UBER_CLIENT_ID")
    os.environ["UBER_CLIENT_ID"] = "unit-test-client"
    try:
        preview = preview_cab_booking(
            provider="uber",
            pickup_location="Marathahalli",
            drop_location="Whitefield",
            rider_name="Aarav Mehta",
            mode="auto",
        )
    finally:
        if previous is None:
            os.environ.pop("UBER_CLIENT_ID", None)
        else:
            os.environ["UBER_CLIENT_ID"] = previous

    assert preview["integration_mode"] == "deeplink"
    assert preview["handoff_url"] is not None
    assert "m.uber.com/ul/" in preview["handoff_url"]
    assert preview["live_booking_supported"] is True


def test_simulated_booking_still_returns_booked_for_local_demo() -> None:
    booking = book_cab(
        provider="uber",
        pickup_location="Marathahalli",
        drop_location="Whitefield",
        rider_name="Aarav Mehta",
        mode="simulate",
    )

    assert booking["status"] == "booked"
    assert booking["integration_mode"] == "simulate"
    assert booking["live_booking_supported"] is False


def test_partner_mode_marks_onboarding_required_for_rapido() -> None:
    response = cab_booking_preview(
        request=type(
            "Request",
            (),
            {
                "provider": "rapido",
                "pickup_location": "Koramangala",
                "drop_location": "MG Road",
                "rider_name": "Field Executive",
                "mode": "auto",
            },
        )()
    )

    assert response["integration_mode"] in {"partner_api", "simulate"}
    if response["integration_mode"] == "partner_api":
        assert response["needs_partner_onboarding"] is True


def test_create_cab_booking_returns_partner_status_for_ola_partner_mode() -> None:
    response = create_cab_booking(
        request=type(
            "Request",
            (),
            {
                "provider": "ola",
                "pickup_location": "HSR Layout",
                "drop_location": "Whitefield",
                "rider_name": "Site Visitor",
                "mode": "partner_api",
            },
        )()
    )

    assert response["status"] == "partner_onboarding_required"
    assert response["integration_mode"] == "partner_api"
