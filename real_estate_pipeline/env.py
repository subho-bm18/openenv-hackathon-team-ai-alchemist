from __future__ import annotations

from copy import deepcopy
from typing import Any

from .cab_booking import book_cab
from .cab_customer_flow import build_cab_notifications, evaluate_cab_eligibility
from .call_flow import build_call_script, summarize_call
from .graders import grade_task
from .models import Action, Observation, OpportunityDetail, OpportunitySummary, PropertyRecord, Reward, StepResult
from .rewards import apply_delta, base_step_penalty, invalid_action_reward
from .tasks import list_task_ids, load_task


class RealEstatePipelineEnv:
    def __init__(self, task_id: str | None = None, max_steps: int = 8):
        self.max_steps = max_steps
        self.task_id = task_id or list_task_ids()[0]
        self._task: dict[str, Any] | None = None
        self._state: dict[str, Any] | None = None
        self._done = False

    def available_tasks(self) -> list[str]:
        return list_task_ids()

    def reset(self, task_id: str | None = None) -> Observation:
        self.task_id = task_id or self.task_id
        task = load_task(self.task_id)
        return self.reset_runtime(task)

    def reset_runtime(self, task: dict[str, Any]) -> Observation:
        self.task_id = task["task_id"]
        self._task = deepcopy(task)
        self._state = self._initial_state_from_task(self._task)
        self._done = False
        return self._build_observation()

    def step(self, action: Action) -> StepResult:
        if self._state is None or self._task is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        if self._done:
            reward = Reward(value=0.0, components={}, penalties=["episode_done"])
            return StepResult(observation=self._build_observation(), reward=reward, done=True, info={"grader_score": self._state["grader_score"]})

        reward = base_step_penalty()
        info: dict[str, Any] = {}
        opportunity = self._state["active_opportunity"]
        expected = self._task["expected"]

        if action.opportunity_id != opportunity["opportunity_id"]:
            reward = invalid_action_reward(action, "wrong_opportunity")
            self._state["last_action_error"] = "Invalid action: wrong opportunity_id"
        else:
            self._apply_action(action, reward, opportunity, expected)

        self._state["step_count"] += 1
        self._state["remaining_steps"] = max(self.max_steps - self._state["step_count"], 0)
        self._state["action_history"].append(action.model_dump())

        grader_score = grade_task(self._task, self._state)
        self._state["grader_score"] = grader_score
        info["grader_score"] = grader_score

        expected_stage = expected.get("stage")
        if opportunity["stage"] in {"visit_scheduled", "builder_appointment_scheduled", "nurture", "deal_closed", "dropped"}:
            self._done = True
        if expected_stage and opportunity["stage"] == expected_stage and expected_stage in {"negotiation", "landlord_meeting_scheduled"}:
            self._done = True
        if self._state["remaining_steps"] <= 0:
            self._done = True

        return StepResult(observation=self._build_observation(), reward=reward, done=self._done, info=info)

    def state(self) -> dict[str, Any]:
        if self._state is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        return deepcopy(self._state)

    def close(self) -> None:
        self._done = True

    def _initial_state_from_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": task["task_id"],
            "step_count": 0,
            "remaining_steps": self.max_steps,
            "queue": [OpportunitySummary(**item).model_dump() for item in deepcopy(task["queue"])],
            "active_opportunity": OpportunityDetail(**deepcopy(task["opportunity"])).model_dump(),
            "inventory_snapshot": [PropertyRecord(**item).model_dump() for item in deepcopy(task["inventory"])],
            "business_rules": deepcopy(task["business_rules"]),
            "last_action_error": None,
            "requested_fields": [],
            "action_history": [],
            "grader_score": 0.0,
        }

    def _build_observation(self) -> Observation:
        assert self._state is not None
        return Observation(
            task_id=self._state["task_id"],
            step_count=self._state["step_count"],
            remaining_steps=self._state["remaining_steps"],
            queue=[OpportunitySummary(**item) for item in self._state["queue"]],
            active_opportunity=OpportunityDetail(**self._state["active_opportunity"]),
            inventory_snapshot=[PropertyRecord(**item) for item in self._state["inventory_snapshot"]],
            business_rules=self._state["business_rules"],
            available_actions=[
                "classify_opportunity",
                "set_priority",
                "request_missing_info",
                "recommend_property",
                "call_customer",
                "confirm_site_visit_interest",
                "check_builder_cab_support",
                "respond_cab_eligibility",
                "book_cab",
                "schedule_visit",
                "schedule_builder_appointment",
                "schedule_landlord_meeting",
                "negotiate_terms",
                "resolve_objection",
                "accept_counter_offer",
                "send_commercial_proposal",
                "close_deal",
                "move_to_nurture",
                "recommend_lease_terms",
                "advance_stage",
                "drop_opportunity",
            ],
            last_action_error=self._state["last_action_error"],
        )

    def _apply_action(self, action: Action, reward: Reward, opportunity: dict[str, Any], expected: dict[str, Any]) -> None:
        if action.action_type == "classify_opportunity":
            opportunity["category"] = action.category
            self._state["last_action_error"] = f"Category set to {action.category}"
            if action.category == expected.get("category"):
                apply_delta(reward, "category", 0.10, signal="correct_category")
            else:
                apply_delta(reward, "category", -0.05, penalty="wrong_category")

        elif action.action_type == "set_priority":
            opportunity["priority"] = action.priority
            self._state["last_action_error"] = f"Priority set to {action.priority}"
            if action.priority == expected.get("priority"):
                apply_delta(reward, "priority", 0.10, signal="correct_priority")
            else:
                apply_delta(reward, "priority", -0.05, penalty="wrong_priority")

        elif action.action_type == "request_missing_info":
            asked = set(action.requested_fields)
            self._state["requested_fields"] = sorted(asked | set(self._state["requested_fields"]))
            opportunity["stage"] = "awaiting_customer"
            self._state["last_action_error"] = "Requested missing details from lead"
            needed = set(expected.get("requested_fields", []))
            if needed and needed.issubset(asked):
                apply_delta(reward, "missing_info", 0.15, signal="requested_required_fields")
            else:
                apply_delta(reward, "missing_info", -0.05, penalty="missing_required_fields")

        elif action.action_type == "recommend_property":
            opportunity["recommended_property_id"] = action.property_id
            self._state["last_action_error"] = f"Recommended property {action.property_id}"
            if action.property_id == expected.get("property_id"):
                apply_delta(reward, "property_match", 0.20, signal="correct_property_match")
            else:
                apply_delta(reward, "property_match", -0.10, penalty="poor_fit_property")

        elif action.action_type == "call_customer":
            transcript, outcome = build_call_script(opportunity, purpose=action.message)
            opportunity["customer_contacted"] = True
            opportunity["call_transcript"] = [turn.model_dump() for turn in transcript]
            opportunity["call_outcome"] = outcome
            opportunity["last_contact_note"] = summarize_call(transcript)
            opportunity["assigned_action"] = "call_customer"
            self._state["last_action_error"] = "Customer called successfully"
            if expected.get("customer_contacted"):
                apply_delta(reward, "customer_contact", 0.10, signal="customer_contacted")
            else:
                apply_delta(reward, "customer_contact", 0.02, signal="customer_contacted")

        elif action.action_type == "confirm_site_visit_interest":
            visit_interest = expected.get("interested_in_visit", True) if action.visit_interest is None else action.visit_interest
            opportunity["interested_in_visit"] = bool(visit_interest)
            opportunity["cab_requested"] = bool(action.cab_requested) if action.cab_requested is not None else bool(visit_interest)
            opportunity["assigned_action"] = "confirm_site_visit_interest"
            if opportunity["interested_in_visit"]:
                self._state["last_action_error"] = "Customer confirmed interest in the site visit"
            else:
                self._state["last_action_error"] = "Customer declined the site visit"
            if opportunity["interested_in_visit"] == expected.get("interested_in_visit", True):
                apply_delta(reward, "visit_interest", 0.10, signal="visit_interest_confirmed")
            else:
                apply_delta(reward, "visit_interest", -0.05, penalty="visit_interest_mismatch")

        elif action.action_type == "check_builder_cab_support":
            property_record = self._property_by_id(opportunity.get("recommended_property_id"))
            eligibility = evaluate_cab_eligibility(opportunity, property_record)
            opportunity["builder_provides_cab"] = eligibility["builder_provides_cab"]
            opportunity["builder_cab_approved"] = eligibility["builder_cab_approved"]
            opportunity["pickup_eligible"] = eligibility["pickup_eligible"]
            opportunity["drop_eligible"] = eligibility["drop_eligible"]
            opportunity["cab_eligibility_status"] = eligibility["cab_eligibility_status"]
            opportunity["cab_customer_response"] = eligibility["cab_customer_response"]
            opportunity["cab_pickup_location"] = eligibility["pickup_location"]
            opportunity["cab_drop_location"] = eligibility["drop_location"]
            opportunity["assigned_action"] = "check_builder_cab_support"
            self._state["last_action_error"] = eligibility["cab_customer_response"]
            if eligibility["builder_provides_cab"] == expected.get("builder_provides_cab", False):
                apply_delta(reward, "builder_cab", 0.08, signal="builder_cab_checked")
            else:
                apply_delta(reward, "builder_cab", -0.05, penalty="builder_cab_mismatch")

        elif action.action_type == "respond_cab_eligibility":
            response_text = opportunity.get("cab_customer_response") or "Cab eligibility has been checked."
            opportunity["assigned_action"] = "respond_cab_eligibility"
            opportunity["last_contact_note"] = response_text
            self._state["last_action_error"] = response_text
            if opportunity.get("cab_eligibility_status") == "eligible":
                apply_delta(reward, "cab_customer_response", 0.08, signal="cab_eligibility_shared")
            else:
                apply_delta(reward, "cab_customer_response", 0.04, signal="cab_eligibility_shared")

        elif action.action_type == "book_cab":
            property_record = self._property_by_id(opportunity.get("recommended_property_id"))
            property_location = property_record.get("location") if property_record else None
            pickup_location = action.pickup_location or opportunity.get("customer_location") or opportunity.get("location")
            drop_location = action.drop_location or property_location
            if not opportunity.get("interested_in_visit"):
                self._state["last_action_error"] = "Cab cannot be booked before customer confirms visit interest"
                apply_delta(reward, "cab_booking", -0.08, penalty="visit_not_confirmed")
            elif not opportunity.get("builder_provides_cab"):
                self._state["last_action_error"] = "Cab cannot be booked because builder cab support is unavailable"
                apply_delta(reward, "cab_booking", -0.08, penalty="builder_cab_unavailable")
            elif not opportunity.get("builder_cab_approved"):
                self._state["last_action_error"] = "Cab cannot be booked because pickup and drop are not eligible after builder approval checks"
                apply_delta(reward, "cab_booking", -0.08, penalty="cab_eligibility_failed")
            elif not property_location:
                self._state["last_action_error"] = "Cab cannot be booked without validating the property location"
                apply_delta(reward, "cab_booking", -0.08, penalty="property_location_missing")
            else:
                try:
                    booking = book_cab(
                        provider=action.cab_provider or "uber",
                        pickup_location=pickup_location or "",
                        drop_location=drop_location or "",
                        rider_name=opportunity.get("customer_name", "Customer"),
                    )
                except ValueError as exc:
                    self._state["last_action_error"] = str(exc)
                    apply_delta(reward, "cab_booking", -0.08, penalty="cab_booking_failed")
                else:
                    opportunity["cab_booking_status"] = booking["status"]
                    opportunity["cab_booking_provider"] = booking["provider"]
                    opportunity["cab_booking_reference"] = booking["booking_reference"]
                    opportunity["cab_booking_mode"] = booking.get("integration_mode")
                    opportunity["cab_pickup_location"] = booking["request_payload"]["pickup_location"]
                    opportunity["cab_drop_location"] = booking["request_payload"]["drop_location"]
                    opportunity["cab_handoff_url"] = booking.get("handoff_url")
                    opportunity["cab_booking_notes"] = booking.get("notes")
                    opportunity["cab_booking_sla_seconds"] = 59
                    opportunity["cab_booked_within_sla"] = True
                    opportunity["cab_notifications"] = [item.model_dump() for item in build_cab_notifications(opportunity)]
                    opportunity["assigned_action"] = "book_cab"
                    self._state["last_action_error"] = (
                        f"{opportunity.get('cab_customer_response') or 'Cab approved.'} "
                        f"Cab booked within 59 seconds via {booking['provider']}. "
                        f"Reference: {booking['booking_reference']}. "
                        "Shared on chat, SMS, and WhatsApp."
                    )
                    if expected.get("cab_booking_status") == "booked":
                        apply_delta(reward, "cab_booking", 0.12, signal="cab_booked")
                    else:
                        apply_delta(reward, "cab_booking", 0.04, signal="cab_booked")

        elif action.action_type == "schedule_visit":
            opportunity["stage"] = "visit_scheduled"
            opportunity["assigned_action"] = "schedule_visit"
            opportunity["appointment_type"] = "site_visit"
            opportunity["appointment_party"] = action.appointment_party or "seller"
            self._state["last_action_error"] = "Site visit scheduled"
            if expected.get("stage") == "visit_scheduled":
                apply_delta(reward, "stage", 0.20, signal="correct_stage_progression")
            else:
                apply_delta(reward, "stage", -0.05, penalty="premature_visit")

        elif action.action_type == "schedule_builder_appointment":
            if expected.get("cab_booking_status") == "booked" and opportunity.get("cab_booking_status") != "booked":
                self._state["last_action_error"] = "Builder appointment should only be scheduled after cab booking is completed"
                apply_delta(reward, "stage", -0.05, penalty="cab_booking_pending")
            else:
                opportunity["stage"] = "builder_appointment_scheduled"
                opportunity["assigned_action"] = "schedule_builder_appointment"
                opportunity["appointment_type"] = "builder_appointment"
                opportunity["appointment_party"] = action.appointment_party or "builder"
                self._state["last_action_error"] = "Builder appointment scheduled"
                if expected.get("stage") == "builder_appointment_scheduled":
                    apply_delta(reward, "stage", 0.20, signal="correct_stage_progression")
                else:
                    apply_delta(reward, "stage", -0.05, penalty="wrong_stage")

        elif action.action_type == "schedule_landlord_meeting":
            opportunity["stage"] = "landlord_meeting_scheduled"
            opportunity["assigned_action"] = "schedule_landlord_meeting"
            opportunity["appointment_type"] = "landlord_meeting"
            opportunity["appointment_party"] = action.appointment_party or "landlord"
            if not opportunity.get("pending_objections"):
                opportunity["pending_objections"] = deepcopy(expected.get("pending_objections", []))
            self._state["last_action_error"] = "Landlord meeting scheduled"
            if expected.get("stage") == "landlord_meeting_scheduled":
                apply_delta(reward, "stage", 0.20, signal="correct_stage_progression")
            else:
                apply_delta(reward, "stage", 0.05, signal="commercial_meeting_booked")

        elif action.action_type == "negotiate_terms":
            opportunity["stage"] = "negotiation"
            opportunity["assigned_action"] = "negotiate_terms"
            opportunity["negotiation_round"] = int(opportunity.get("negotiation_round", 0)) + 1
            if action.lease_terms:
                opportunity["lease_terms"] = action.lease_terms.model_dump()
            if opportunity.get("negotiation_round") == 1 and not opportunity.get("landlord_counter_offer"):
                expected_counter = expected.get("landlord_counter_offer")
                if expected_counter:
                    opportunity["landlord_counter_offer"] = deepcopy(expected_counter)
            self._state["last_action_error"] = "Commercial terms negotiated"
            if expected.get("stage") == "negotiation":
                apply_delta(reward, "stage", 0.20, signal="correct_stage_progression")
            else:
                apply_delta(reward, "stage", 0.10, signal="commercial_negotiation_started")

        elif action.action_type == "resolve_objection":
            resolved = set(action.objections_resolved)
            pending = [item for item in opportunity.get("pending_objections", []) if item not in resolved]
            opportunity["pending_objections"] = pending
            opportunity["assigned_action"] = "resolve_objection"
            self._state["last_action_error"] = "Commercial objections addressed"
            expected_objections = set(expected.get("pending_objections", []))
            if expected_objections and resolved:
                ratio = len(resolved & expected_objections) / len(expected_objections)
                apply_delta(reward, "objection_resolution", 0.12 * ratio, signal="objections_addressed")
            elif resolved:
                apply_delta(reward, "objection_resolution", 0.05, signal="objections_addressed")

        elif action.action_type == "accept_counter_offer":
            counter_offer = opportunity.get("landlord_counter_offer")
            opportunity["assigned_action"] = "accept_counter_offer"
            if counter_offer:
                opportunity["lease_terms"] = deepcopy(counter_offer)
                opportunity["landlord_counter_offer"] = None
                self._state["last_action_error"] = "Landlord counter-offer accepted"
                apply_delta(reward, "counter_offer", 0.10, signal="counter_offer_accepted")
            else:
                self._state["last_action_error"] = "No landlord counter-offer available"
                apply_delta(reward, "counter_offer", -0.05, penalty="missing_counter_offer")

        elif action.action_type == "send_commercial_proposal":
            opportunity["proposal_sent"] = True
            opportunity["assigned_action"] = "send_commercial_proposal"
            self._state["last_action_error"] = "Commercial proposal sent"
            apply_delta(reward, "proposal", 0.08, signal="proposal_shared")

        elif action.action_type == "close_deal":
            opportunity["stage"] = "deal_closed"
            opportunity["deal_closed"] = True
            opportunity["closing_value"] = action.closing_value or opportunity.get("closing_value")
            opportunity["assigned_action"] = "close_deal"
            if opportunity.get("pending_objections"):
                self._state["last_action_error"] = "Commercial deal cannot close with unresolved objections"
                opportunity["deal_closed"] = False
                opportunity["stage"] = "negotiation"
                apply_delta(reward, "deal_closed", -0.08, penalty="unresolved_objections")
            else:
                self._state["last_action_error"] = "Commercial deal closed"
                if expected.get("deal_closed"):
                    apply_delta(reward, "deal_closed", 0.25, signal="deal_closed")
                else:
                    apply_delta(reward, "deal_closed", 0.05, signal="deal_closed")
            if expected.get("deal_closed") and opportunity.get("deal_closed"):
                apply_delta(reward, "deal_closed", 0.25, signal="deal_closed")

        elif action.action_type == "move_to_nurture":
            opportunity["stage"] = "nurture"
            opportunity["assigned_action"] = "move_to_nurture"
            self._state["last_action_error"] = "Lead moved to nurture"
            if expected.get("stage") == "nurture":
                apply_delta(reward, "stage", 0.20, signal="correct_nurture_progression")
            else:
                apply_delta(reward, "stage", -0.05, penalty="wrong_stage")

        elif action.action_type == "recommend_lease_terms":
            opportunity["lease_terms"] = action.lease_terms.model_dump() if action.lease_terms else None
            self._state["last_action_error"] = "Lease terms recommended"
            actual = opportunity["lease_terms"] or {}
            expected_terms = expected.get("lease_terms", {})
            if actual and actual.get("lease_years") == expected_terms.get("lease_years"):
                apply_delta(reward, "lease_terms", 0.15, signal="lease_terms_in_range")
            else:
                apply_delta(reward, "lease_terms", -0.10, penalty="unrealistic_lease_terms")

        elif action.action_type == "advance_stage":
            opportunity["stage"] = action.stage or "negotiation"
            opportunity["assigned_action"] = "advance_stage"
            self._state["last_action_error"] = f"Advanced stage to {opportunity['stage']}"
            if opportunity["stage"] == expected.get("stage"):
                apply_delta(reward, "stage", 0.20, signal="correct_stage_progression")
            else:
                apply_delta(reward, "stage", -0.05, penalty="wrong_stage")

        elif action.action_type == "drop_opportunity":
            opportunity["stage"] = "dropped"
            opportunity["assigned_action"] = "drop_opportunity"
            self._state["last_action_error"] = "Opportunity dropped"
            apply_delta(reward, "drop", -0.10, penalty="dropped_live_opportunity")

        else:
            invalid = invalid_action_reward(action, "unknown_action")
            reward.value = invalid.value
            reward.components = invalid.components
            reward.progress_signals = invalid.progress_signals
            reward.penalties = invalid.penalties
            self._state["last_action_error"] = "Unknown action"

    def _property_by_id(self, property_id: str | None) -> dict[str, Any] | None:
        if not property_id:
            return None
        for property_record in self._state.get("inventory_snapshot", []):
            if property_record.get("property_id") == property_id:
                return property_record
        return None
