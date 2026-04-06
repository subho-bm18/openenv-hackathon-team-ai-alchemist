from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import time
from typing import Any

from .env import RealEstatePipelineEnv
from .models import (
    Action,
    AgentDecision,
    InboundLead,
    LeadSimulationResult,
    LeaseTerms,
    LiveTrafficSimulationResponse,
    Observation,
    PropertyRecord,
)
from .policy import (
    best_property_match,
    choose_category,
    choose_priority,
    recommended_lease_terms,
)


DEFAULT_INVENTORY: list[dict[str, Any]] = [
    {
        "property_id": "res_prop_101",
        "segment": "residential",
        "title": "2BHK in Whitefield near metro",
        "location": "Whitefield",
        "price_type": "sale",
        "price": 9200000,
        "details": {"property_type": "2BHK apartment", "bedrooms": 2, "builder_cab_available": True},
    },
    {
        "property_id": "res_prop_102",
        "segment": "residential",
        "title": "3BHK in Sarjapur",
        "location": "Sarjapur",
        "price_type": "sale",
        "price": 11800000,
        "details": {"property_type": "3BHK apartment", "bedrooms": 3, "builder_cab_available": False},
    },
    {
        "property_id": "com_prop_301",
        "segment": "commercial",
        "title": "Retail corner shell in CBD",
        "location": "CBD Retail District",
        "price_type": "lease",
        "price": 315000,
        "details": {"square_feet": 2800, "fit_for": "retail_food", "frontage": "high"},
    },
]


DEFAULT_LIVE_LEADS: list[InboundLead] = [
    InboundLead(
        lead_id="live_res_001",
        customer_name="Aarav Mehta",
        inquiry="Looking for a 2BHK apartment in Whitefield. Budget is 95 lakhs and I want to move in within 30 days. Please suggest options.",
        segment="residential",
        profession="software engineer",
        total_experience_years=7,
        employment_type="salaried",
        customer_location="Marathahalli",
        budget=9500000,
        location="Whitefield",
        timeline_days=30,
        property_type="2BHK apartment",
    )
]


DEFAULT_STREAM_LEADS: list[InboundLead] = [
    *DEFAULT_LIVE_LEADS,
    InboundLead(
        lead_id="live_res_002",
        customer_name="Neha Singh",
        inquiry="I am looking for a 3-bedroom home on the west side. Please share options.",
        segment="residential",
        profession="marketing consultant",
        employment_type="business",
        customer_location="Banashankari",
        location="West Side",
        property_type="3-bedroom home",
        missing_fields=["budget", "timeline_days", "financing_status", "total_experience_years"],
    ),
    InboundLead(
        lead_id="live_com_001",
        customer_name="Bean Street Cafe",
        inquiry="We need 2500 to 3000 square feet in a high-footfall retail street. Our opening target is in 45 days. We can stretch to 3.2 lakh monthly if the fit and frontage are strong.",
        segment="commercial",
        profession="founder",
        total_experience_years=11,
        employment_type="business",
        customer_location="Indiranagar",
        budget=320000,
        location="CBD Retail District",
        timeline_days=45,
        business_type="cafe",
        square_feet_min=2500,
        square_feet_max=3000,
    ),
]


class LiveTrafficAgent:
    def choose_action(self, observation: Observation) -> tuple[str, Action]:
        opportunity = observation.active_opportunity
        opportunity_id = opportunity.opportunity_id

        if not opportunity.category:
            category = choose_category(opportunity)
            return (
                "Classify the inbound lead first so downstream routing and scoring rules apply.",
                Action(action_type="classify_opportunity", opportunity_id=opportunity_id, category=category),
            )

        if not opportunity.priority:
            priority = choose_priority(opportunity)
            return (
                "Set priority from lead clarity and urgency to ensure fast follow-up for strong opportunities.",
                Action(action_type="set_priority", opportunity_id=opportunity_id, priority=priority),
            )

        if opportunity.missing_fields and opportunity.stage == "new":
            return (
                "Collect the missing qualification fields before recommending a property or advancing the deal.",
                Action(
                    action_type="request_missing_info",
                    opportunity_id=opportunity_id,
                    requested_fields=opportunity.missing_fields,
                    message=f"Please share {', '.join(opportunity.missing_fields)} so we can shortlist the best options.",
                ),
            )

        if not opportunity.recommended_property_id:
            best_property = best_property_match(opportunity, observation.inventory_snapshot)
            if best_property is None:
                return (
                    "No suitable inventory is available yet, so keep the lead warm instead of forcing a poor recommendation.",
                    Action(
                        action_type="move_to_nurture",
                        opportunity_id=opportunity_id,
                        message="No good-fit listing is available right now. Keep this lead in nurture for follow-up.",
                    ),
                )
            return (
                "Recommend the closest inventory match based on budget, location, and property intent.",
                Action(
                    action_type="recommend_property",
                    opportunity_id=opportunity_id,
                    property_id=best_property.property_id,
                ),
            )

        if opportunity.segment == "commercial" and not opportunity.lease_terms:
            lease_terms = recommended_lease_terms(opportunity, observation.inventory_snapshot)
            return (
                "For commercial demand, propose credible lease terms before moving the deal into negotiation.",
                Action(
                    action_type="recommend_lease_terms",
                    opportunity_id=opportunity_id,
                    lease_terms=lease_terms,
                ),
            )

        if opportunity.recommended_property_id and not opportunity.customer_contacted:
            contact_purpose = "confirm the shortlisted property and align on next meeting"
            if opportunity.segment == "commercial":
                contact_purpose = "confirm the shortlisted property, commercials, and landlord meeting availability"
            return (
                "Call the customer to confirm interest and align everyone on the next concrete appointment.",
                Action(
                    action_type="call_customer",
                    opportunity_id=opportunity_id,
                    message=f"Called the customer to {contact_purpose}.",
                ),
            )

        if opportunity.segment == "residential" and opportunity.customer_contacted and opportunity.interested_in_visit is None:
            return (
                "The residential lead is qualified, so confirm whether the customer actually wants to take the site visit.",
                Action(
                    action_type="confirm_site_visit_interest",
                    opportunity_id=opportunity_id,
                    visit_interest=True,
                    cab_requested=True,
                    message="Confirmed whether the customer wants to visit the shortlisted property.",
                ),
            )

        if opportunity.segment == "residential" and opportunity.interested_in_visit is False:
            return (
                "The customer is not ready for a visit yet, so keep the lead in nurture until interest changes.",
                Action(
                    action_type="move_to_nurture",
                    opportunity_id=opportunity_id,
                    message="Customer is not ready for a site visit yet. Keep the lead warm in nurture.",
                ),
            )

        if opportunity.segment == "residential" and opportunity.interested_in_visit and opportunity.builder_provides_cab is None:
            return (
                "Before arranging transport, verify builder approval and whether both pickup and drop are eligible for the shortlisted property.",
                Action(
                    action_type="check_builder_cab_support",
                    opportunity_id=opportunity_id,
                    property_id=opportunity.recommended_property_id,
                    message="Checked builder approval and pickup/drop eligibility for cab support.",
                ),
            )

        if (
            opportunity.segment == "residential"
            and opportunity.interested_in_visit
            and opportunity.cab_requested
            and opportunity.cab_eligibility_status
            and opportunity.cab_booking_status != "booked"
            and opportunity.assigned_action != "respond_cab_eligibility"
        ):
            return (
                "Share the eligibility result with the customer before attempting the booking so the pickup and drop outcome is explicit.",
                Action(
                    action_type="respond_cab_eligibility",
                    opportunity_id=opportunity_id,
                    message="Shared the cab pickup and drop eligibility result with the customer.",
                ),
            )

        if (
            opportunity.segment == "residential"
            and opportunity.interested_in_visit
            and opportunity.builder_provides_cab
            and opportunity.builder_cab_approved
            and opportunity.cab_booking_status != "booked"
        ):
            return (
                "The customer wants to visit, pickup and drop are eligible, and the builder approved cab support, so place the booking immediately.",
                Action(
                    action_type="book_cab",
                    opportunity_id=opportunity_id,
                    property_id=opportunity.recommended_property_id,
                    cab_provider=_preferred_cab_provider(opportunity),
                    pickup_location=opportunity.customer_location or opportunity.location,
                    message="Booked a cab for the customer site visit after confirming pickup and property location.",
                ),
            )

        if opportunity.segment == "commercial":
            if opportunity.stage == "landlord_meeting_scheduled":
                return (
                    "After the landlord meeting, move into active negotiation on the commercial terms.",
                    Action(
                        action_type="negotiate_terms",
                        opportunity_id=opportunity_id,
                        lease_terms=opportunity.lease_terms,
                        message="Negotiated commercials and lock-in structure with the landlord.",
                    ),
                )
            if opportunity.pending_objections:
                return (
                    "Address the landlord objections before asking for final approval on the proposal.",
                    Action(
                        action_type="resolve_objection",
                        opportunity_id=opportunity_id,
                        objections_resolved=opportunity.pending_objections,
                        message="Resolved the landlord's objections on deposit, fit-out, and lock-in.",
                    ),
                )
            if opportunity.landlord_counter_offer:
                return (
                    "Accept the landlord counter-offer when it still fits the tenant budget and deal logic.",
                    Action(
                        action_type="accept_counter_offer",
                        opportunity_id=opportunity_id,
                        message="Accepted the landlord counter-offer and updated the working commercial terms.",
                    ),
                )
            if opportunity.stage == "negotiation" and not opportunity.proposal_sent:
                return (
                    "Once the commercials are aligned, issue the formal proposal before closing.",
                    Action(
                        action_type="send_commercial_proposal",
                        opportunity_id=opportunity_id,
                        message="Sent the commercial proposal with negotiated terms for final sign-off.",
                    ),
                )
            if opportunity.stage == "negotiation" and opportunity.proposal_sent:
                closing_value = None
                if opportunity.lease_terms:
                    terms = opportunity.lease_terms.model_dump() if hasattr(opportunity.lease_terms, "model_dump") else opportunity.lease_terms
                    closing_value = int(terms.get("monthly_rent", 0)) * int(terms.get("lease_years", 0)) * 12
                return (
                    "The proposal is out and aligned, so close the commercial deal.",
                    Action(
                        action_type="close_deal",
                        opportunity_id=opportunity_id,
                        closing_value=closing_value,
                        message="Closed the lease with the landlord and tenant on the negotiated terms.",
                    ),
                )
            if opportunity.stage != "landlord_meeting_scheduled":
                return (
                    "Property fit, terms, and customer confirmation are in place, so book the landlord meeting.",
                    Action(
                        action_type="schedule_landlord_meeting",
                        opportunity_id=opportunity_id,
                        property_id=opportunity.recommended_property_id,
                        appointment_party="landlord",
                        message="Booked a landlord meeting to review terms and move toward negotiation.",
                    ),
                )
            return (
                "Continue commercial follow-up with the landlord side until the deal is closed.",
                Action(
                    action_type="schedule_landlord_meeting",
                    opportunity_id=opportunity_id,
                    property_id=opportunity.recommended_property_id,
                    appointment_party="landlord",
                    message="Reconfirming the landlord meeting to keep the process moving.",
                ),
            )

        if opportunity.missing_fields:
            return (
                "The lead still needs customer input, so move it to nurture instead of forcing a site visit.",
                Action(
                    action_type="move_to_nurture",
                    opportunity_id=opportunity_id,
                    message="Lead remains active until the missing qualification details are collected.",
                ),
            )

        return (
            "The lead is qualified, matched, and transport prerequisites are complete, so the next best action is to book the builder appointment.",
            Action(
                action_type="schedule_builder_appointment",
                opportunity_id=opportunity_id,
                property_id=opportunity.recommended_property_id,
                appointment_party="builder",
                message="Booked the builder appointment for a guided site visit.",
            ),
        )


def build_runtime_task(lead: InboundLead, inventory: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    inventory_snapshot = deepcopy(inventory or DEFAULT_INVENTORY)
    segment = lead.segment
    opportunity_id = lead.lead_id
    category = choose_category(lead)
    priority = choose_priority(lead)

    task: dict[str, Any] = {
        "task_id": f"live_{opportunity_id}",
        "difficulty": "live",
        "queue": [
            {
                "opportunity_id": opportunity_id,
                "segment": segment,
                "title": _title_from_lead(lead),
                "stage": "new",
                "priority": None,
            }
        ],
        "opportunity": {
            "opportunity_id": opportunity_id,
            "segment": segment,
            "customer_name": lead.customer_name,
            "inquiry": lead.inquiry,
            "profession": lead.profession,
            "total_experience_years": lead.total_experience_years,
            "employment_type": lead.employment_type,
            "preferred_cab_provider": lead.preferred_cab_provider,
            "customer_location": lead.customer_location,
            "budget": lead.budget,
            "location": lead.location,
            "timeline_days": lead.timeline_days,
            "property_type": lead.property_type,
            "business_type": lead.business_type,
            "square_feet_min": lead.square_feet_min,
            "square_feet_max": lead.square_feet_max,
            "missing_fields": lead.missing_fields,
            "notes": ["Lead ingested from CRM traffic simulator"],
        },
        "inventory": inventory_snapshot,
        "business_rules": _business_rules_for(segment),
        "expected": {
            "category": category,
            "priority": priority,
            "customer_contacted": True,
            "weights": {
                "category": 0.15,
                "priority": 0.15,
                "property_match": 0.2,
                "customer_contact": 0.1,
                "stage": 0.2,
            },
        },
    }

    matching_property = _expected_property(task["opportunity"], inventory_snapshot)
    if matching_property:
        task["expected"]["property_id"] = matching_property["property_id"]

    if lead.missing_fields:
        task["expected"]["requested_fields"] = lead.missing_fields
        task["expected"]["stage"] = "nurture"
        task["expected"]["customer_contacted"] = False
        task["expected"]["weights"] = {
            "category": 0.2,
            "priority": 0.2,
            "missing_info": 0.3,
            "stage": 0.3,
        }
    elif matching_property is None:
        task["expected"]["stage"] = "nurture"
        task["expected"]["customer_contacted"] = False
        task["expected"]["weights"] = {
            "category": 0.3,
            "priority": 0.3,
            "stage": 0.4,
        }
    elif segment == "commercial":
        lease_terms = recommended_lease_terms(task["opportunity"], [PropertyRecord(**item) for item in inventory_snapshot])
        landlord_counter_offer = {
            "lease_years": lease_terms.lease_years,
            "monthly_rent": min((lead.budget or 0) + 5000, (lease_terms.monthly_rent or 0) + 5000) if lead.budget else lease_terms.monthly_rent,
            "deposit_months": max((lease_terms.deposit_months or 0), 6),
            "fit_out_support": lease_terms.fit_out_support,
        }
        task["expected"]["lease_terms"] = landlord_counter_offer
        task["expected"]["pending_objections"] = [
            "deposit_months",
            "fit_out_support",
        ]
        task["expected"]["landlord_counter_offer"] = landlord_counter_offer
        task["expected"]["proposal_sent"] = True
        task["expected"]["deal_closed"] = True
        task["expected"]["weights"] = {
            "category": 0.1,
            "priority": 0.1,
            "property_match": 0.2,
            "lease_terms": 0.15,
            "customer_contact": 0.1,
            "stage": 0.15,
            "proposal_sent": 0.1,
            "deal_closed": 0.1,
        }
        task["expected"]["stage"] = "deal_closed"
    else:
        builder_provides_cab = bool((matching_property.get("details") or {}).get("builder_cab_available")) if matching_property else False
        task["expected"]["interested_in_visit"] = True
        task["expected"]["cab_requested"] = True
        task["expected"]["builder_provides_cab"] = builder_provides_cab
        if builder_provides_cab:
            task["expected"]["builder_cab_approved"] = True
            task["expected"]["pickup_eligible"] = True
            task["expected"]["drop_eligible"] = True
            task["expected"]["cab_booking_status"] = "booked"
            task["expected"]["weights"].update(
                {
                    "visit_interest": 0.1,
                    "builder_cab": 0.05,
                    "cab_booking": 0.05,
                }
            )
        else:
            task["expected"]["weights"].update(
                {
                    "visit_interest": 0.1,
                    "builder_cab": 0.05,
                }
            )
        task["expected"]["stage"] = "builder_appointment_scheduled"

    return task


def simulate_live_traffic(
    leads: list[InboundLead] | None = None,
    inventory: list[dict[str, Any]] | None = None,
) -> LiveTrafficSimulationResponse:
    run_id = datetime.now(timezone.utc).strftime("live-%Y%m%d%H%M%S")
    leads_to_process = leads or DEFAULT_LIVE_LEADS
    results = [process_live_lead(lead, inventory=inventory) for lead in leads_to_process]
    return LiveTrafficSimulationResponse(run_id=run_id, processed_leads=len(results), results=results)


def process_live_lead(
    lead: InboundLead,
    inventory: list[dict[str, Any]] | None = None,
) -> LeadSimulationResult:
    task = build_runtime_task(lead, inventory=inventory)
    return process_runtime_task(task, lead_id=lead.lead_id)


def process_runtime_task(task: dict[str, Any], lead_id: str | None = None) -> LeadSimulationResult:
    agent = LiveTrafficAgent()
    max_steps = 11 if task.get("opportunity", {}).get("segment") == "commercial" else 9
    env = RealEstatePipelineEnv(max_steps=max_steps)
    observation = env.reset_runtime(task)
    trace: list[AgentDecision] = []

    for step in range(1, env.max_steps + 1):
        thought, action = agent.choose_action(observation)
        result = env.step(action)
        trace.append(
            AgentDecision(
                step=step,
                thought=thought,
                action=action,
                reward=result.reward.value,
                done=result.done,
                grader_score=float(result.info.get("grader_score", 0.0)),
                last_action_result=result.observation.last_action_result,
            )
        )
        observation = result.observation
        if result.done:
            break

    final_state = env.state()
    active = final_state["active_opportunity"]
    return LeadSimulationResult(
        lead_id=lead_id or active["opportunity_id"],
        task_id=task["task_id"],
        success=final_state["grader_score"] >= 0.75,
        final_score=final_state["grader_score"],
        final_stage=active["stage"],
        recommended_property_id=active.get("recommended_property_id"),
        assigned_action=active.get("assigned_action"),
        action_trace=trace,
        final_state=final_state,
    )


def stream_live_traffic_events(
    leads: list[InboundLead] | None = None,
    delay_seconds: float = 0.0,
) -> Any:
    run_id = datetime.now(timezone.utc).strftime("live-%Y%m%d%H%M%S")
    leads_to_process = leads or DEFAULT_STREAM_LEADS
    completed_results: list[dict[str, Any]] = []

    yield _stream_event(
        event_type="run_started",
        run_id=run_id,
        payload={"processed_leads": len(leads_to_process)},
    )

    for lead in leads_to_process:
        yield _stream_event(
            event_type="lead_received",
            run_id=run_id,
            lead_id=lead.lead_id,
            payload={"customer_name": lead.customer_name, "inquiry": lead.inquiry, "segment": lead.segment},
        )

        task = build_runtime_task(lead)
        max_steps = 11 if lead.segment == "commercial" else 9
        env = RealEstatePipelineEnv(max_steps=max_steps)
        observation = env.reset_runtime(task)
        agent = LiveTrafficAgent()

        for step in range(1, env.max_steps + 1):
            thought, action = agent.choose_action(observation)
            result = env.step(action)
            payload = {
                "step": step,
                "thought": thought,
                "action": action.model_dump(exclude_none=True),
                "reward": result.reward.value,
                "done": result.done,
                "grader_score": float(result.info.get("grader_score", 0.0)),
                "last_action_result": result.observation.last_action_result,
            }
            if action.action_type == "call_customer":
                payload["call_outcome"] = result.observation.active_opportunity.call_outcome
                payload["call_transcript"] = [turn.model_dump() for turn in result.observation.active_opportunity.call_transcript]
            if action.action_type in {"check_builder_cab_support", "respond_cab_eligibility", "book_cab"}:
                payload["cab_customer_response"] = result.observation.active_opportunity.cab_customer_response
                payload["pickup_eligible"] = result.observation.active_opportunity.pickup_eligible
                payload["drop_eligible"] = result.observation.active_opportunity.drop_eligible
                payload["builder_cab_approved"] = result.observation.active_opportunity.builder_cab_approved
                payload["cab_booking_reference"] = result.observation.active_opportunity.cab_booking_reference
                payload["cab_notifications"] = [
                    item.model_dump() for item in result.observation.active_opportunity.cab_notifications
                ]
            yield _stream_event(
                event_type="lead_step",
                run_id=run_id,
                lead_id=lead.lead_id,
                payload=payload,
            )
            observation = result.observation
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            if result.done:
                break

        final_result = process_live_lead(lead)
        completed_results.append(
            {
                "lead_id": final_result.lead_id,
                "success": final_result.success,
                "final_score": final_result.final_score,
                "final_stage": final_result.final_stage,
                "recommended_property_id": final_result.recommended_property_id,
            }
        )
        yield _stream_event(
            event_type="lead_completed",
            run_id=run_id,
            lead_id=lead.lead_id,
            payload={
                "success": final_result.success,
                "final_score": final_result.final_score,
                "final_stage": final_result.final_stage,
                "recommended_property_id": final_result.recommended_property_id,
                "assigned_action": final_result.assigned_action,
            },
        )

    yield _stream_event(
        event_type="run_completed",
        run_id=run_id,
        payload={
            "processed_leads": len(completed_results),
            "results": completed_results,
        },
    )


def _title_from_lead(lead: InboundLead) -> str:
    if lead.segment == "commercial":
        return f"{lead.business_type or 'Commercial'} inquiry in {lead.location or 'target market'}"
    return f"{lead.property_type or 'Residential'} buyer in {lead.location or 'target location'}"


def _business_rules_for(segment: str) -> list[str]:
    if segment == "commercial":
        return [
            "Commercial tenants with clear budget, area needs, and timeline should be prioritized high.",
            "Recommend only assets that fit location, size, and budget expectations.",
            "Advance to negotiation after asset fit and credible lease terms are established.",
        ]
    return [
        "High-intent residential leads with clear budget and timeline should be prioritized high.",
        "Recommend a listing only if it matches both budget and location intent.",
        "If critical qualification fields are missing, ask for them before scheduling a visit.",
    ]


def _expected_property(opportunity: dict[str, Any], inventory: list[dict[str, Any]]) -> dict[str, Any] | None:
    matched = best_property_match(opportunity, [PropertyRecord(**item) for item in inventory])
    return matched.model_dump() if matched else None


def _preferred_cab_provider(opportunity: Observation | Any) -> str:
    preferred_provider = getattr(opportunity, "preferred_cab_provider", None) if not isinstance(opportunity, dict) else opportunity.get("preferred_cab_provider")
    if preferred_provider:
        return preferred_provider
    employment_type = getattr(opportunity, "employment_type", None) if not isinstance(opportunity, dict) else opportunity.get("employment_type")
    return "uber" if employment_type == "salaried" else "ola"


def _stream_event(
    event_type: str,
    run_id: str,
    payload: dict[str, Any],
    lead_id: str | None = None,
) -> str:
    body = {
        "event": event_type,
        "run_id": run_id,
        "lead_id": lead_id,
        "payload": payload,
    }
    return json.dumps(body) + "\n"
