import asyncio
import json

from app import live_dashboard, simulate_live_stream_custom
from real_estate_pipeline.models import InboundLead, LiveTrafficSimulationRequest
from real_estate_pipeline.live_simulator import (
    DEFAULT_LIVE_LEADS,
    DEFAULT_STREAM_LEADS,
    build_runtime_task,
    simulate_live_traffic,
    stream_live_traffic_events,
)


def test_build_runtime_task_sets_expected_whitefield_flow() -> None:
    lead = DEFAULT_LIVE_LEADS[0]
    task = build_runtime_task(lead)

    assert task["expected"]["category"] == "residential_buyer"
    assert task["expected"]["priority"] == "high"
    assert task["expected"]["property_id"] == "res_prop_101"
    assert task["expected"]["customer_contacted"] is True
    assert task["expected"]["stage"] == "builder_appointment_scheduled"


def test_simulate_live_traffic_executes_end_to_end_residential_flow() -> None:
    response = simulate_live_traffic(DEFAULT_LIVE_LEADS)

    assert response.processed_leads == 1
    result = response.results[0]
    assert result.success is True
    assert result.final_score == 1.0
    assert result.final_stage == "builder_appointment_scheduled"
    assert result.recommended_property_id == "res_prop_101"
    assert len(result.action_trace) == 5
    assert result.action_trace[0].action.action_type == "classify_opportunity"
    assert result.action_trace[1].action.action_type == "set_priority"
    assert result.action_trace[2].action.action_type == "recommend_property"
    assert result.action_trace[3].action.action_type == "call_customer"
    assert result.action_trace[4].action.action_type == "schedule_builder_appointment"


def test_stream_live_traffic_emits_run_and_completion_events() -> None:
    events = [json.loads(event) for event in stream_live_traffic_events(DEFAULT_STREAM_LEADS[:1], delay_seconds=0.0)]

    assert events[0]["event"] == "run_started"
    assert any(event["event"] == "lead_step" for event in events)
    assert any(event["payload"].get("call_transcript") for event in events if event["event"] == "lead_step")
    assert any(event["event"] == "lead_completed" for event in events)
    assert events[-1]["event"] == "run_completed"


def test_live_dashboard_contains_stream_controls() -> None:
    response = live_dashboard()
    body = response.body.decode("utf-8")

    assert "Live Lead Processing Dashboard" in body
    assert "Manual Lead Entry" in body
    assert "/simulate/live/stream" in body
    assert "Load Commercial Example" in body
    assert "commercial-group hidden" in body


def test_custom_stream_endpoint_returns_manual_lead_events() -> None:
    request = LiveTrafficSimulationRequest(
        leads=[
            InboundLead(
                lead_id="manual_demo_001",
                customer_name="Manual Demo Buyer",
                inquiry="Looking for a 2BHK apartment in Whitefield with a budget of 95 lakhs.",
                segment="residential",
                budget=9500000,
                location="Whitefield",
                timeline_days=21,
                property_type="2BHK apartment",
            )
        ]
    )
    response = simulate_live_stream_custom(request, 0.0)

    async def collect_first_and_last() -> tuple[str, str]:
        items: list[str] = []
        async for item in response.body_iterator:
            items.append(item)
        return items[0], items[-1]

    first, last = asyncio.run(collect_first_and_last())
    first_event = json.loads(first)
    last_event = json.loads(last)

    assert first_event["event"] == "run_started"
    assert last_event["event"] == "run_completed"


def test_commercial_flow_reaches_deal_closed() -> None:
    response = simulate_live_traffic([DEFAULT_STREAM_LEADS[-1]])

    result = response.results[0]
    assert result.final_stage == "deal_closed"
    assert result.final_state["active_opportunity"]["proposal_sent"] is True
    assert result.final_state["active_opportunity"]["deal_closed"] is True
    assert result.final_state["active_opportunity"]["pending_objections"] == []
    assert result.final_state["active_opportunity"]["landlord_counter_offer"] is None
    assert [step.action.action_type for step in result.action_trace] == [
        "classify_opportunity",
        "set_priority",
        "recommend_property",
        "recommend_lease_terms",
        "call_customer",
        "schedule_landlord_meeting",
        "negotiate_terms",
        "resolve_objection",
        "accept_counter_offer",
        "send_commercial_proposal",
        "close_deal",
    ]
