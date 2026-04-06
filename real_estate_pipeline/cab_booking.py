from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus


SUPPORTED_CAB_PROVIDERS = {"ola", "rapido", "uber"}

PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "uber": {
        "display_name": "Uber",
        "officially_verified": True,
        "verification_date": "2026-04-05",
        "supports_public_deeplink": True,
        "supports_partner_api": True,
        "supports_self_serve_public_api": False,
        "default_live_mode": "deeplink",
        "docs_url": "https://developer.uber.com/products/ride-requests",
        "contact_url": "https://developer.uber.com/products/ride-requests",
        "notes": (
            "Uber Ride Requests is publicly documented. The most practical production path "
            "for this project is an Uber app deep link, while direct API booking requires "
            "app registration, tokens, and partner-grade credentials."
        ),
        "required_env": {
            "deeplink": ["UBER_CLIENT_ID"],
            "partner_api": ["UBER_CLIENT_ID", "UBER_SERVER_TOKEN"],
        },
    },
    "ola": {
        "display_name": "Ola",
        "officially_verified": True,
        "verification_date": "2026-04-05",
        "supports_public_deeplink": False,
        "supports_partner_api": True,
        "supports_self_serve_public_api": False,
        "default_live_mode": "partner_api",
        "docs_url": "https://corporate.olacabs.com/tutorial.html",
        "contact_url": "https://corporate.olacabs.com/#/home",
        "notes": (
            "Ola has verifiable corporate and partner booking flows. The public material we "
            "could verify points to partner dashboard and enterprise onboarding rather than a "
            "current self-serve public booking API."
        ),
        "required_env": {
            "partner_api": ["OLA_CORPORATE_ACCOUNT", "OLA_PARTNER_TOKEN"],
        },
    },
    "rapido": {
        "display_name": "Rapido",
        "officially_verified": True,
        "verification_date": "2026-04-05",
        "supports_public_deeplink": False,
        "supports_partner_api": True,
        "supports_self_serve_public_api": False,
        "default_live_mode": "partner_api",
        "docs_url": "https://www.rapido.bike/CorporatePartners",
        "contact_url": "https://www.rapido.bike/CorporatePartners",
        "notes": (
            "Rapido publicly advertises App / API access for corporate travel, but we did not "
            "find a self-serve public developer booking spec. Production use should be treated "
            "as a partner-onboarding flow."
        ),
        "required_env": {
            "partner_api": ["RAPIDO_CORPORATE_ACCOUNT", "RAPIDO_PARTNER_TOKEN"],
        },
    },
}


def list_cab_providers() -> list[dict[str, Any]]:
    return [get_cab_provider(provider) for provider in sorted(PROVIDER_CATALOG)]


def get_cab_provider(provider: str) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    provider_data = deepcopy(PROVIDER_CATALOG[normalized_provider])
    provider_data["provider"] = normalized_provider
    provider_data["runtime_status"] = _runtime_status(normalized_provider)
    return provider_data


def preview_cab_booking(
    provider: str,
    pickup_location: str,
    drop_location: str,
    rider_name: str,
    mode: str = "auto",
) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    if not pickup_location or not drop_location:
        raise ValueError("Both pickup and drop locations are required for cab booking.")

    provider_meta = get_cab_provider(normalized_provider)
    runtime_status = provider_meta["runtime_status"]
    requested_mode = _resolve_mode(normalized_provider, mode)
    effective_mode = requested_mode

    handoff_url = None
    if requested_mode == "auto":
        effective_mode = "simulate"
        if runtime_status["deeplink_ready"]:
            effective_mode = "deeplink"
        elif runtime_status["partner_api_ready"]:
            effective_mode = "partner_api"

    if effective_mode == "deeplink":
        handoff_url = _build_handoff_url(normalized_provider, pickup_location, drop_location)
    elif effective_mode == "partner_api":
        handoff_url = provider_meta["contact_url"]

    return {
        "provider": normalized_provider,
        "display_name": provider_meta["display_name"],
        "mode_requested": mode,
        "integration_mode": effective_mode,
        "live_booking_supported": effective_mode in {"deeplink", "partner_api"},
        "needs_partner_onboarding": effective_mode == "partner_api" and not runtime_status["partner_api_ready"],
        "handoff_url": handoff_url,
        "provider_notes": provider_meta["notes"],
        "verification": {
            "officially_verified": provider_meta["officially_verified"],
            "verification_date": provider_meta["verification_date"],
            "docs_url": provider_meta["docs_url"],
        },
        "request_payload": {
            "rider_name": rider_name,
            "pickup_location": pickup_location,
            "drop_location": drop_location,
        },
        "runtime_status": runtime_status,
    }


def book_cab(
    provider: str,
    pickup_location: str,
    drop_location: str,
    rider_name: str,
    mode: str = "simulate",
) -> dict[str, Any]:
    preview = preview_cab_booking(
        provider=provider,
        pickup_location=pickup_location,
        drop_location=drop_location,
        rider_name=rider_name,
        mode=mode,
    )
    normalized_provider = preview["provider"]
    reference = f"{normalized_provider.upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    if preview["integration_mode"] == "simulate":
        return {
            "provider": normalized_provider,
            "request_payload": preview["request_payload"],
            "booking_reference": reference,
            "status": "booked",
            "integration_mode": "simulate",
            "live_booking_supported": False,
            "handoff_url": None,
            "notes": "Demo-safe simulated booking completed inside the local environment.",
            "verification": preview["verification"],
        }

    if preview["integration_mode"] == "deeplink":
        return {
            "provider": normalized_provider,
            "request_payload": preview["request_payload"],
            "booking_reference": reference,
            "status": "handoff_required",
            "integration_mode": "deeplink",
            "live_booking_supported": True,
            "handoff_url": preview["handoff_url"],
            "notes": "User confirmation is required in the provider app or web handoff flow.",
            "verification": preview["verification"],
        }

    return {
        "provider": normalized_provider,
        "request_payload": preview["request_payload"],
        "booking_reference": reference,
        "status": "partner_onboarding_required",
        "integration_mode": "partner_api",
        "live_booking_supported": True,
        "handoff_url": preview["handoff_url"],
        "notes": "This provider path is partner-managed and needs enterprise onboarding before live booking can occur.",
        "verification": preview["verification"],
    }


def _normalize_provider(provider: str) -> str:
    normalized_provider = provider.strip().lower()
    if normalized_provider not in SUPPORTED_CAB_PROVIDERS:
        raise ValueError(f"Unsupported cab provider: {provider}")
    return normalized_provider


def _resolve_mode(provider: str, mode: str) -> str:
    normalized_mode = (mode or "auto").strip().lower()
    if normalized_mode not in {"auto", "simulate", "deeplink", "partner_api"}:
        raise ValueError(f"Unsupported cab booking mode: {mode}")
    if normalized_mode == "deeplink" and not PROVIDER_CATALOG[provider]["supports_public_deeplink"]:
        raise ValueError(f"{PROVIDER_CATALOG[provider]['display_name']} does not expose a verified public deeplink flow in this project.")
    if normalized_mode == "partner_api" and not PROVIDER_CATALOG[provider]["supports_partner_api"]:
        raise ValueError(f"{PROVIDER_CATALOG[provider]['display_name']} does not expose a verified partner API flow in this project.")
    return normalized_mode


def _runtime_status(provider: str) -> dict[str, Any]:
    provider_meta = PROVIDER_CATALOG[provider]
    required_env = provider_meta.get("required_env", {})
    deeplink_env = required_env.get("deeplink", [])
    partner_env = required_env.get("partner_api", [])

    deeplink_ready = bool(deeplink_env) and all(os.getenv(item) for item in deeplink_env)
    partner_api_ready = bool(partner_env) and all(os.getenv(item) for item in partner_env)

    return {
        "deeplink_ready": deeplink_ready,
        "partner_api_ready": partner_api_ready,
        "deeplink_missing_env": [item for item in deeplink_env if not os.getenv(item)],
        "partner_api_missing_env": [item for item in partner_env if not os.getenv(item)],
        "can_simulate": True,
        "recommended_project_mode": _recommended_project_mode(provider, deeplink_ready, partner_api_ready),
    }


def _recommended_project_mode(provider: str, deeplink_ready: bool, partner_api_ready: bool) -> str:
    if deeplink_ready:
        return "deeplink"
    if partner_api_ready:
        return "partner_api"
    default_live_mode = PROVIDER_CATALOG[provider]["default_live_mode"]
    if default_live_mode == "deeplink":
        return "simulate_then_deeplink"
    return "simulate_then_partner_api"


def _build_handoff_url(provider: str, pickup_location: str, drop_location: str) -> str | None:
    if provider == "uber":
        client_id = os.getenv("UBER_CLIENT_ID", "demo-client")
        return (
            "https://m.uber.com/ul/?action=setPickup"
            f"&client_id={quote_plus(client_id)}"
            f"&pickup[formatted_address]={quote_plus(pickup_location)}"
            f"&dropoff[formatted_address]={quote_plus(drop_location)}"
        )
    return None
