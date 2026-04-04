from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LeaseTerms(BaseModel):
    lease_years: int | None = None
    monthly_rent: int | None = None
    deposit_months: int | None = None
    fit_out_support: bool | None = None


class CallTurn(BaseModel):
    speaker: Literal["agent", "customer"]
    text: str


class OpportunitySummary(BaseModel):
    opportunity_id: str
    segment: Literal["residential", "commercial"]
    title: str
    stage: str
    priority: str | None = None


class PropertyRecord(BaseModel):
    property_id: str
    segment: Literal["residential", "commercial"]
    title: str
    location: str
    price_type: Literal["sale", "rent", "lease"]
    price: int
    details: dict[str, Any] = Field(default_factory=dict)


class OpportunityDetail(BaseModel):
    opportunity_id: str
    segment: Literal["residential", "commercial"]
    customer_name: str
    inquiry: str
    budget: int | None = None
    location: str | None = None
    timeline_days: int | None = None
    property_type: str | None = None
    business_type: str | None = None
    square_feet_min: int | None = None
    square_feet_max: int | None = None
    missing_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    stage: str = "new"
    category: str | None = None
    priority: str | None = None
    recommended_property_id: str | None = None
    lease_terms: LeaseTerms | None = None
    customer_contacted: bool = False
    last_contact_note: str | None = None
    call_outcome: str | None = None
    call_transcript: list[CallTurn] = Field(default_factory=list)
    appointment_type: str | None = None
    appointment_party: str | None = None
    proposal_sent: bool = False
    deal_closed: bool = False
    closing_value: int | None = None
    negotiation_round: int = 0
    pending_objections: list[str] = Field(default_factory=list)
    landlord_counter_offer: LeaseTerms | None = None
    assigned_action: str | None = None


class Observation(BaseModel):
    task_id: str
    step_count: int
    remaining_steps: int
    queue: list[OpportunitySummary]
    active_opportunity: OpportunityDetail
    inventory_snapshot: list[PropertyRecord]
    business_rules: list[str]
    available_actions: list[str]
    last_action_result: str | None = None


class Reward(BaseModel):
    value: float
    components: dict[str, float] = Field(default_factory=dict)
    progress_signals: list[str] = Field(default_factory=list)
    penalties: list[str] = Field(default_factory=list)


class Action(BaseModel):
    action_type: Literal[
        "classify_opportunity",
        "set_priority",
        "request_missing_info",
        "recommend_property",
        "call_customer",
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
    ]
    opportunity_id: str
    category: str | None = None
    priority: str | None = None
    requested_fields: list[str] = Field(default_factory=list)
    property_id: str | None = None
    message: str | None = None
    appointment_party: str | None = None
    closing_value: int | None = None
    lease_terms: LeaseTerms | None = None
    objections_resolved: list[str] = Field(default_factory=list)
    stage: str | None = None
    reason: str | None = None


class StepResult(BaseModel):
    observation: Observation
    reward: Reward
    done: bool
    info: dict[str, Any] = Field(default_factory=dict)


class InboundLead(BaseModel):
    lead_id: str
    customer_name: str
    inquiry: str
    segment: Literal["residential", "commercial"] = "residential"
    budget: int | None = None
    location: str | None = None
    timeline_days: int | None = None
    property_type: str | None = None
    business_type: str | None = None
    square_feet_min: int | None = None
    square_feet_max: int | None = None
    missing_fields: list[str] = Field(default_factory=list)


class AgentDecision(BaseModel):
    step: int
    thought: str
    action: Action
    reward: float
    done: bool
    grader_score: float
    last_action_result: str | None = None


class LeadSimulationResult(BaseModel):
    lead_id: str
    task_id: str
    success: bool
    final_score: float
    final_stage: str
    recommended_property_id: str | None = None
    assigned_action: str | None = None
    action_trace: list[AgentDecision] = Field(default_factory=list)
    final_state: dict[str, Any] = Field(default_factory=dict)


class LiveTrafficSimulationRequest(BaseModel):
    leads: list[InboundLead] = Field(default_factory=list)


class LiveTrafficSimulationResponse(BaseModel):
    run_id: str
    processed_leads: int
    results: list[LeadSimulationResult] = Field(default_factory=list)
