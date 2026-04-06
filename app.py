from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from real_estate_pipeline import Action, RealEstatePipelineEnv
from real_estate_pipeline.cab_booking import book_cab, list_cab_providers, preview_cab_booking
from real_estate_pipeline.graders import grade_task
from real_estate_pipeline.live_simulator import (
    DEFAULT_LIVE_LEADS,
    DEFAULT_STREAM_LEADS,
    process_live_lead,
    simulate_live_traffic,
    stream_live_traffic_events,
)
from real_estate_pipeline.models import InboundLead, LiveTrafficSimulationRequest, LiveTrafficSimulationResponse
from real_estate_pipeline.tasks import load_task


app = FastAPI(title="Real Estate Pipeline OpenEnv", version="0.1.0")
env = RealEstatePipelineEnv()
latest_call_cache: dict[str, object] = {}


class ResetRequest(BaseModel):
    task_id: str | None = None


class CabBookingRequest(BaseModel):
    provider: str
    pickup_location: str
    drop_location: str
    rider_name: str
    mode: str = "auto"


class CabEligibilityMockRequest(BaseModel):
    customer_name: str
    inquiry: str
    customer_location: str
    property_location: str
    property_type: str = "2BHK apartment"
    budget: int | None = None
    timeline_days: int | None = None
    profession: str | None = None
    employment_type: str | None = None
    total_experience_years: int | None = None
    provider: str = "uber"
    builder_cab_available: bool = True


@app.get("/")
def root() -> dict[str, object]:
    return {
        "name": "real-estate-pipeline-openenv",
        "status": "ok",
        "tasks": env.available_tasks(),
    }


@app.post("/reset")
def reset(request: ResetRequest | None = None) -> dict[str, object]:
    observation = env.reset(task_id=request.task_id if request else None)
    return {"observation": observation.model_dump(), "done": False}


@app.post("/step")
def step(action: Action) -> dict[str, object]:
    try:
        result = env.step(action)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()


@app.get("/state")
def state() -> dict[str, object]:
    try:
        return env.state()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/calls/latest")
def latest_call() -> dict[str, object]:
    try:
        current_state = env.state()
    except RuntimeError:
        if latest_call_cache:
            return latest_call_cache
        return {
            "available": False,
            "detail": "No active or cached call transcript is available yet.",
            "call_transcript": [],
        }

    opportunity = current_state["active_opportunity"]
    if opportunity.get("call_transcript"):
        return {
            "available": True,
            "opportunity_id": opportunity["opportunity_id"],
            "customer_name": opportunity["customer_name"],
            "customer_contacted": opportunity.get("customer_contacted", False),
            "call_outcome": opportunity.get("call_outcome"),
            "last_contact_note": opportunity.get("last_contact_note"),
            "call_transcript": opportunity.get("call_transcript", []),
        }
    if latest_call_cache:
        return latest_call_cache
    return {
        "available": False,
        "detail": "No active or cached call transcript is available yet.",
        "call_transcript": [],
    }


@app.get("/cab/providers")
def cab_providers() -> dict[str, object]:
    return {"providers": list_cab_providers()}


@app.post("/cab/bookings/preview")
def cab_booking_preview(request: CabBookingRequest) -> dict[str, object]:
    try:
        return preview_cab_booking(
            provider=request.provider,
            pickup_location=request.pickup_location,
            drop_location=request.drop_location,
            rider_name=request.rider_name,
            mode=request.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/cab/bookings")
def create_cab_booking(request: CabBookingRequest) -> dict[str, object]:
    try:
        return book_cab(
            provider=request.provider,
            pickup_location=request.pickup_location,
            drop_location=request.drop_location,
            rider_name=request.rider_name,
            mode=request.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/cab/mock-flow")
def cab_mock_flow(request: CabEligibilityMockRequest) -> dict[str, object]:
    inventory = [
        {
            "property_id": "mock_res_prop_001",
            "segment": "residential",
            "title": f"{request.property_type} in {request.property_location}",
            "location": request.property_location,
            "price_type": "sale",
            "price": request.budget or 9500000,
            "details": {
                "property_type": request.property_type,
                "builder_cab_available": request.builder_cab_available,
            },
        }
    ]
    lead = InboundLead(
        lead_id="mock_cab_flow_001",
        customer_name=request.customer_name,
        inquiry=request.inquiry,
        segment="residential",
        profession=request.profession,
        total_experience_years=request.total_experience_years,
        employment_type=request.employment_type,
        preferred_cab_provider=request.provider,
        customer_location=request.customer_location,
        budget=request.budget,
        location=request.property_location,
        timeline_days=request.timeline_days,
        property_type=request.property_type,
    )
    result = process_live_lead(lead, inventory=inventory)
    active = result.final_state["active_opportunity"]
    customer_response = active.get("cab_customer_response") or active.get("last_contact_note")
    return {
        "lead_id": result.lead_id,
        "final_stage": result.final_stage,
        "cab_flow": {
            "customer_wants_cab": active.get("cab_requested"),
            "builder_cab_available": active.get("builder_provides_cab"),
            "builder_cab_approved": active.get("builder_cab_approved"),
            "pickup_eligible": active.get("pickup_eligible"),
            "drop_eligible": active.get("drop_eligible"),
            "eligibility_status": active.get("cab_eligibility_status"),
            "customer_response": customer_response,
            "cab_booking_status": active.get("cab_booking_status"),
            "cab_booking_reference": active.get("cab_booking_reference"),
            "cab_booking_sla_seconds": active.get("cab_booking_sla_seconds"),
            "cab_booked_within_sla": active.get("cab_booked_within_sla"),
            "notifications": active.get("cab_notifications", []),
        },
        "action_trace": [step.action.model_dump(exclude_none=True) for step in result.action_trace],
    }


@app.get("/tasks")
def tasks() -> dict[str, object]:
    entries = []
    for task_id in env.available_tasks():
        task = load_task(task_id)
        entries.append(
            {
                "task_id": task["task_id"],
                "difficulty": task["difficulty"],
                "segment": task["opportunity"]["segment"],
            }
        )
    return {"tasks": entries}


@app.get("/simulate/live-example", response_model=LiveTrafficSimulationResponse)
def simulate_live_example() -> LiveTrafficSimulationResponse:
    return simulate_live_traffic(DEFAULT_LIVE_LEADS)


@app.post("/simulate/live", response_model=LiveTrafficSimulationResponse)
def simulate_live(request: LiveTrafficSimulationRequest | None = None) -> LiveTrafficSimulationResponse:
    leads = request.leads if request and request.leads else DEFAULT_LIVE_LEADS
    return simulate_live_traffic(leads)


@app.get("/simulate/live/stream")
def simulate_live_stream(delay_seconds: float = 0.35) -> StreamingResponse:
    stream = _cache_call_stream(stream_live_traffic_events(DEFAULT_STREAM_LEADS, delay_seconds=max(delay_seconds, 0.0)))
    return StreamingResponse(stream, media_type="application/x-ndjson")


@app.post("/simulate/live/stream")
def simulate_live_stream_custom(
    request: LiveTrafficSimulationRequest | None = None,
    delay_seconds: float = 0.35,
) -> StreamingResponse:
    leads = request.leads if request and request.leads else DEFAULT_STREAM_LEADS
    stream = _cache_call_stream(stream_live_traffic_events(leads, delay_seconds=max(delay_seconds, 0.0)))
    return StreamingResponse(stream, media_type="application/x-ndjson")


def _cache_call_stream(stream):
    for raw_event in stream:
        try:
            event = json.loads(raw_event)
        except json.JSONDecodeError:
            yield raw_event
            continue

        payload = event.get("payload", {})
        if event.get("event") == "lead_step" and payload.get("call_transcript"):
            latest_call_cache.clear()
            latest_call_cache.update(
                {
                    "opportunity_id": event.get("lead_id"),
                    "customer_name": payload.get("customer_name") or event.get("lead_id"),
                    "available": True,
                    "customer_contacted": True,
                    "call_outcome": payload.get("call_outcome"),
                    "last_contact_note": _last_customer_turn(payload.get("call_transcript", [])),
                    "call_transcript": payload.get("call_transcript", []),
                }
            )
        yield raw_event


def _last_customer_turn(call_transcript: list[dict[str, object]]) -> str | None:
    for turn in reversed(call_transcript):
        if turn.get("speaker") == "customer":
            text = turn.get("text")
            return text if isinstance(text, str) else None
    return None


@app.get("/dashboard/live", response_class=HTMLResponse)
def live_dashboard() -> HTMLResponse:
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Live CRM Traffic Dashboard</title>
  <style>
    :root {
      --bg: linear-gradient(135deg, #f7f4ea 0%, #dce8f2 48%, #f4dbc9 100%);
      --panel: rgba(255, 255, 255, 0.78);
      --ink: #1f2c2d;
      --muted: #5e6a6b;
      --accent: #0d7c66;
      --accent-soft: #d8efe8;
      --warn: #b76e2b;
      --border: rgba(31, 44, 45, 0.12);
      --shadow: 0 18px 50px rgba(31, 44, 45, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background: var(--bg);
      min-height: 100vh;
    }
    .shell {
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }
    .hero {
      display: grid;
      gap: 14px;
      margin-bottom: 24px;
    }
    .eyebrow {
      font-size: 12px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--muted);
    }
    h1 {
      margin: 0;
      font-size: clamp(2rem, 5vw, 4rem);
      line-height: 0.95;
      max-width: 10ch;
    }
    .sub {
      max-width: 62ch;
      font-size: 1.05rem;
      color: var(--muted);
    }
    .controls, .grid > section {
      border: 1px solid var(--border);
      background: var(--panel);
      backdrop-filter: blur(16px);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 14px;
      padding: 18px;
      margin-bottom: 18px;
    }
    button {
      border: none;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      padding: 12px 18px;
      font: inherit;
      cursor: pointer;
    }
    button:disabled { opacity: 0.55; cursor: wait; }
    .status {
      color: var(--muted);
      font-size: 0.95rem;
    }
    .grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 18px;
    }
    section {
      padding: 18px;
      min-height: 420px;
    }
    h2 {
      margin: 0 0 14px;
      font-size: 1.15rem;
    }
    .lead-card, .event-row {
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 14px;
      background: rgba(255, 255, 255, 0.72);
    }
    .cab-panel {
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      background: rgba(247, 250, 244, 0.9);
      margin-bottom: 18px;
    }
    .cab-status-list {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    .cab-status-item {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.82);
      border: 1px solid var(--border);
      font-size: 0.95rem;
    }
    .cab-status-item .label {
      color: var(--muted);
    }
    .cab-status-item .value {
      font-weight: 700;
      color: var(--ink);
      text-align: right;
    }
    .cab-status-item.active .value {
      color: var(--accent);
    }
    .cab-status-item.good .value {
      color: #1c7c54;
    }
    .cab-status-item.bad .value {
      color: #a44a3f;
    }
    .cab-message {
      margin-top: 12px;
      padding: 12px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.82);
      border: 1px solid var(--border);
      color: var(--ink);
      min-height: 24px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 18px;
    }
    .form-grid .full {
      grid-column: 1 / -1;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 0.9rem;
      color: var(--muted);
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(255, 255, 255, 0.85);
      font: inherit;
      color: var(--ink);
    }
    textarea {
      min-height: 96px;
      resize: vertical;
    }
    .form-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 18px;
    }
    .secondary {
      background: #d9e7e4;
      color: #24453f;
    }
    .voice {
      background: #355c7d;
    }
    .voice-panel {
      border: 1px dashed var(--border);
      border-radius: 18px;
      padding: 14px;
      margin-bottom: 18px;
      background: rgba(242, 248, 250, 0.85);
    }
    .voice-log {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.92rem;
      min-height: 22px;
    }
    .segment-group.hidden {
      display: none;
    }
    .lead-list, .event-list {
      display: grid;
      gap: 12px;
      max-height: 70vh;
      overflow: auto;
      padding-right: 4px;
    }
    .lead-meta {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-size: 0.9rem;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .score {
      display: inline-block;
      margin-top: 10px;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.9rem;
    }
    .event-tag {
      display: inline-block;
      margin-bottom: 8px;
      padding: 4px 8px;
      border-radius: 999px;
      background: #efe4d3;
      color: var(--warn);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.84rem;
      color: #263536;
    }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
      h1 { max-width: none; }
      .form-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="hero">
      <div class="eyebrow">Agentic CRM Demo</div>
      <h1>Live Lead Processing Dashboard</h1>
      <div class="sub">Streams multiple simulated inbound leads the way a brokerage inbox might receive them, then shows how the autonomous agent qualifies, prioritizes, matches inventory, and moves each deal forward.</div>
    </div>
    <div class="controls">
      <button id="startButton">Start Stream</button>
      <div class="status" id="statusText">Ready to simulate inbound CRM traffic.</div>
    </div>
    <div class="grid">
      <section>
        <h2>Manual Lead Entry</h2>
        <div class="voice-panel">
          <div><strong>Voice Assistant</strong></div>
          <div class="sub">Use your microphone to capture a lead verbally or play back the latest simulated call flow. Best supported in Chromium-based browsers.</div>
          <div class="form-actions" style="margin-top: 12px; margin-bottom: 0;">
            <button id="startVoiceIntakeButton" class="voice">Start Voice Intake</button>
            <button id="dictateInquiryButton" class="voice">Dictate Inquiry</button>
            <button id="playLatestCallButton" class="secondary">Play Latest Call</button>
          </div>
          <div class="voice-log" id="voiceLog">Voice assistant idle.</div>
        </div>
        <div class="form-grid">
          <label>
            Lead ID
            <input id="leadId" value="manual_res_001" />
          </label>
          <label>
            Customer Name
            <input id="customerName" value="Demo Buyer" />
          </label>
          <label>
            Profession
            <input id="profession" value="software engineer" />
          </label>
          <label>
            Employment Type
            <select id="employmentType">
              <option value="salaried" selected>salaried</option>
              <option value="business">business</option>
              <option value="self-employed">self-employed</option>
            </select>
          </label>
          <label>
            Segment
            <select id="segment">
              <option value="residential" selected>residential</option>
              <option value="commercial">commercial</option>
            </select>
          </label>
          <label>
            Location
            <input id="location" value="Whitefield" />
          </label>
          <label>
            Customer Current Location
            <input id="customerLocation" value="Marathahalli" />
          </label>
          <label>
            Budget
            <input id="budget" type="number" value="9500000" />
          </label>
          <label>
            Timeline Days
            <input id="timelineDays" type="number" value="30" />
          </label>
          <label>
            Total Experience (Years)
            <input id="totalExperienceYears" type="number" value="7" />
          </label>
          <label class="segment-group residential-group">
            Property Type
            <input id="propertyType" value="2BHK apartment" />
          </label>
          <label class="segment-group commercial-group hidden">
            Business Type
            <input id="businessType" value="" placeholder="Use for commercial leads" />
          </label>
          <label class="segment-group commercial-group hidden">
            Square Feet Min
            <input id="squareFeetMin" type="number" value="" />
          </label>
          <label class="segment-group commercial-group hidden">
            Square Feet Max
            <input id="squareFeetMax" type="number" value="" />
          </label>
          <label class="full">
            Inquiry
            <textarea id="inquiry">Looking for a 2BHK apartment in Whitefield. Budget is 95 lakhs and I want to move in within 30 days. Please suggest options.</textarea>
          </label>
          <label class="full">
            Missing Fields
            <input id="missingFields" value="" placeholder="Comma-separated, for example: budget,timeline_days,financing_status" />
          </label>
        </div>
        <div class="form-actions">
          <button id="submitManualButton">Run Manual Lead</button>
          <button id="loadDefaultButton" class="secondary">Load Whitefield Example</button>
          <button id="loadCommercialButton" class="secondary">Load Commercial Example</button>
        </div>
        <h2>Cab Operations</h2>
        <div class="cab-panel">
          <div class="sub">Residential lead runs update this section with cab eligibility, booking progress, notifications, and SLA timing.</div>
          <div class="cab-status-list" id="cabStatusList">
            <div class="cab-status-item"><span class="label">Cab Eligibility</span><span class="value">Awaiting residential lead</span></div>
            <div class="cab-status-item"><span class="label">Builder Approval</span><span class="value">Not checked</span></div>
            <div class="cab-status-item"><span class="label">Pickup Eligibility</span><span class="value">Not checked</span></div>
            <div class="cab-status-item"><span class="label">Drop Eligibility</span><span class="value">Not checked</span></div>
            <div class="cab-status-item"><span class="label">Cab Booking</span><span class="value">Awaiting confirmation</span></div>
            <div class="cab-status-item"><span class="label">Booking Reference</span><span class="value">Pending</span></div>
            <div class="cab-status-item"><span class="label">Cab Timing SLA</span><span class="value">Pending</span></div>
            <div class="cab-status-item"><span class="label">Chat Notification</span><span class="value">Pending</span></div>
            <div class="cab-status-item"><span class="label">SMS Notification</span><span class="value">Pending</span></div>
            <div class="cab-status-item"><span class="label">WhatsApp Notification</span><span class="value">Pending</span></div>
          </div>
          <div class="cab-message" id="cabMessage">Run a residential lead to see the cab operations flow.</div>
        </div>
        <h2>Lead Outcomes</h2>
        <div class="lead-list" id="leadList"></div>
      </section>
      <section>
        <h2>Live Event Feed</h2>
        <div class="event-list" id="eventList"></div>
      </section>
    </div>
  </div>
  <script>
    const startButton = document.getElementById("startButton");
    const statusText = document.getElementById("statusText");
    const leadList = document.getElementById("leadList");
    const eventList = document.getElementById("eventList");
    const cabStatusList = document.getElementById("cabStatusList");
    const cabMessage = document.getElementById("cabMessage");
    const submitManualButton = document.getElementById("submitManualButton");
    const loadDefaultButton = document.getElementById("loadDefaultButton");
    const loadCommercialButton = document.getElementById("loadCommercialButton");
    const segmentSelect = document.getElementById("segment");
    const startVoiceIntakeButton = document.getElementById("startVoiceIntakeButton");
    const dictateInquiryButton = document.getElementById("dictateInquiryButton");
    const playLatestCallButton = document.getElementById("playLatestCallButton");
    const voiceLog = document.getElementById("voiceLog");
    const leads = new Map();
    const cabVoiceState = new Map();
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    const recognitionSupported = Boolean(SpeechRecognition);
    const playbackSupported = Boolean(window.speechSynthesis);
    let recognitionBusy = false;

    function renderLeadCard(leadId) {
      const lead = leads.get(leadId);
      if (!lead) return;
      let card = document.getElementById(`lead-${leadId}`);
      if (!card) {
        card = document.createElement("div");
        card.className = "lead-card";
        card.id = `lead-${leadId}`;
        leadList.prepend(card);
      }
      card.innerHTML = `
        <div class="lead-meta">
          <strong>${lead.customer_name || leadId}</strong>
          <span>${leadId}</span>
        </div>
        <div>${lead.inquiry || ""}</div>
        ${lead.last_contact_note ? `<div class="score">Call Note: ${lead.last_contact_note}</div>` : ""}
        <div class="score">Stage: ${lead.final_stage || lead.stage || "receiving"} | Score: ${lead.final_score ?? lead.grader_score ?? 0}</div>
      `;
    }

    function addEventRow(event) {
      const row = document.createElement("div");
      row.className = "event-row";
      row.innerHTML = `<div class="event-tag">${event.event}</div><pre>${JSON.stringify(event, null, 2)}</pre>`;
      eventList.prepend(row);
    }

    function resetCabPanel() {
      cabStatusList.innerHTML = `
        <div class="cab-status-item"><span class="label">Cab Eligibility</span><span class="value">Awaiting residential lead</span></div>
        <div class="cab-status-item"><span class="label">Builder Approval</span><span class="value">Not checked</span></div>
        <div class="cab-status-item"><span class="label">Pickup Eligibility</span><span class="value">Not checked</span></div>
        <div class="cab-status-item"><span class="label">Drop Eligibility</span><span class="value">Not checked</span></div>
        <div class="cab-status-item"><span class="label">Cab Booking</span><span class="value">Awaiting confirmation</span></div>
        <div class="cab-status-item"><span class="label">Booking Reference</span><span class="value">Pending</span></div>
        <div class="cab-status-item"><span class="label">Cab Timing SLA</span><span class="value">Pending</span></div>
        <div class="cab-status-item"><span class="label">Chat Notification</span><span class="value">Pending</span></div>
        <div class="cab-status-item"><span class="label">SMS Notification</span><span class="value">Pending</span></div>
        <div class="cab-status-item"><span class="label">WhatsApp Notification</span><span class="value">Pending</span></div>
      `;
      cabMessage.textContent = "Run a residential lead to see the cab operations flow.";
    }

    function setCabStatus(label, value, tone = "") {
      const rows = Array.from(cabStatusList.querySelectorAll(".cab-status-item"));
      const row = rows.find((item) => item.querySelector(".label")?.textContent === label);
      if (!row) return;
      row.classList.remove("active", "good", "bad");
      if (tone) {
        row.classList.add(tone);
      }
      const valueNode = row.querySelector(".value");
      if (valueNode) {
        valueNode.textContent = value;
      }
    }

    function updateCabPanelFromPayload(payload, lead = {}) {
      if (!payload) return;
      if (lead.segment === "commercial") {
        cabMessage.textContent = "Cab operations are only shown for residential leads in this dashboard.";
        return;
      }
      const voiceState = cabVoiceState.get(lead.customer_name || "default") || {
        initiationAnnounced: false,
        bookedAnnounced: false,
        notificationsAnnounced: false,
      };

      if (payload.action?.action_type === "confirm_site_visit_interest") {
        setCabStatus("Cab Eligibility", "Awaiting builder approval", "active");
        setCabStatus("Cab Booking", "Awaiting cab booking", "active");
        cabMessage.textContent = "Customer has confirmed site-visit interest and asked for cab support.";
      }

      if (payload.builder_cab_approved !== undefined || payload.pickup_eligible !== undefined || payload.drop_eligible !== undefined) {
        const eligible = Boolean(payload.builder_cab_approved && payload.pickup_eligible && payload.drop_eligible);
        setCabStatus("Builder Approval", payload.builder_cab_approved ? "Approved" : "Not approved", payload.builder_cab_approved ? "good" : "bad");
        setCabStatus("Pickup Eligibility", payload.pickup_eligible ? "Eligible" : "Not eligible", payload.pickup_eligible ? "good" : "bad");
        setCabStatus("Drop Eligibility", payload.drop_eligible ? "Eligible" : "Not eligible", payload.drop_eligible ? "good" : "bad");
        setCabStatus("Cab Eligibility", eligible ? "Cab eligible" : "Cab not eligible", eligible ? "good" : "bad");
      }

      if (payload.cab_customer_response) {
        cabMessage.textContent = payload.cab_customer_response;
      }

      if (
        payload.action?.action_type === "respond_cab_eligibility"
        && payload.builder_cab_approved
        && !voiceState.initiationAnnounced
      ) {
        voiceState.initiationAnnounced = true;
        const providerHint = document.getElementById("employmentType").value === "salaried" ? "Uber" : "Ola";
        const announcement = `${payload.cab_customer_response} We are now initiating your cab booking with ${providerHint}. Please wait up to 59 seconds while I fetch the booking details.`;
        voiceLog.textContent = announcement;
        playBeep(700, 140);
        speak(announcement);
      }

      if (payload.action?.action_type === "book_cab") {
        setCabStatus("Cab Booking", payload.cab_booking_reference ? "Cab booked" : "Awaiting cab booking", payload.cab_booking_reference ? "good" : "active");
      }

      if (payload.cab_booking_reference) {
        setCabStatus("Booking Reference", payload.cab_booking_reference, "good");
        setCabStatus("Cab Timing SLA", "Booked within 59 seconds", "good");
        if (!voiceState.bookedAnnounced) {
          voiceState.bookedAnnounced = true;
          const providerName = payload.action?.cab_provider
            || lead.preferred_cab_provider
            || (document.getElementById("employmentType").value === "salaried" ? "Uber" : "Ola");
          const bookedMessage = `Your cab has been booked with ${providerName}. Your booking reference is ${payload.cab_booking_reference}.`;
          voiceLog.textContent = bookedMessage;
          playBeep(760, 140);
          speak(bookedMessage);
        }
      }

      const notifications = payload.cab_notifications || [];
      const byChannel = new Map(notifications.map((item) => [item.channel, item]));
      if (byChannel.has("chat")) {
        setCabStatus("Chat Notification", "Notification sent", "good");
      }
      if (byChannel.has("sms")) {
        setCabStatus("SMS Notification", "Notification sent", "good");
      }
      if (byChannel.has("whatsapp")) {
        setCabStatus("WhatsApp Notification", "Notification sent", "good");
      }
      if (notifications.length && !voiceState.notificationsAnnounced) {
        voiceState.notificationsAnnounced = true;
        const notificationMessage = "The cab details have also been shared on chat, SMS, and WhatsApp.";
        voiceLog.textContent = notificationMessage;
        playBeep(820, 120);
        speak(notificationMessage);
      }
      cabVoiceState.set(lead.customer_name || "default", voiceState);
    }

    function resetBoards() {
      leadList.innerHTML = "";
      eventList.innerHTML = "";
      leads.clear();
      cabVoiceState.clear();
      resetCabPanel();
    }

    function manualPayload() {
      const numberOrNull = (value) => value === "" ? null : Number(value);
      const rawMissing = document.getElementById("missingFields").value.trim();
      return {
        leads: [
          {
            lead_id: document.getElementById("leadId").value.trim() || "manual_lead_001",
            customer_name: document.getElementById("customerName").value.trim() || "Demo Lead",
            inquiry: document.getElementById("inquiry").value.trim(),
            segment: document.getElementById("segment").value,
            profession: document.getElementById("profession").value.trim() || null,
            total_experience_years: numberOrNull(document.getElementById("totalExperienceYears").value.trim()),
            employment_type: document.getElementById("employmentType").value || null,
            customer_location: document.getElementById("customerLocation").value.trim() || null,
            budget: numberOrNull(document.getElementById("budget").value.trim()),
            location: document.getElementById("location").value.trim() || null,
            timeline_days: numberOrNull(document.getElementById("timelineDays").value.trim()),
            property_type: document.getElementById("propertyType").value.trim() || null,
            business_type: document.getElementById("businessType").value.trim() || null,
            square_feet_min: numberOrNull(document.getElementById("squareFeetMin").value.trim()),
            square_feet_max: numberOrNull(document.getElementById("squareFeetMax").value.trim()),
            missing_fields: rawMissing ? rawMissing.split(",").map(item => item.trim()).filter(Boolean) : []
          }
        ]
      };
    }

    function loadWhitefieldExample() {
      document.getElementById("leadId").value = "manual_res_001";
      document.getElementById("customerName").value = "Aarav Mehta";
      document.getElementById("profession").value = "software engineer";
      document.getElementById("employmentType").value = "salaried";
      document.getElementById("segment").value = "residential";
      document.getElementById("location").value = "Whitefield";
      document.getElementById("customerLocation").value = "Marathahalli";
      document.getElementById("budget").value = "9500000";
      document.getElementById("timelineDays").value = "30";
      document.getElementById("totalExperienceYears").value = "7";
      document.getElementById("propertyType").value = "2BHK apartment";
      document.getElementById("businessType").value = "";
      document.getElementById("squareFeetMin").value = "";
      document.getElementById("squareFeetMax").value = "";
      document.getElementById("inquiry").value = "Looking for a 2BHK apartment in Whitefield. Budget is 95 lakhs and I want to move in within 30 days. Please suggest options.";
      document.getElementById("missingFields").value = "";
      syncSegmentFields();
    }

    function loadCommercialExample() {
      document.getElementById("leadId").value = "manual_com_001";
      document.getElementById("customerName").value = "Bean Street Cafe";
      document.getElementById("profession").value = "founder";
      document.getElementById("employmentType").value = "business";
      document.getElementById("segment").value = "commercial";
      document.getElementById("location").value = "CBD Retail District";
      document.getElementById("customerLocation").value = "Indiranagar";
      document.getElementById("budget").value = "320000";
      document.getElementById("timelineDays").value = "45";
      document.getElementById("totalExperienceYears").value = "11";
      document.getElementById("propertyType").value = "";
      document.getElementById("businessType").value = "cafe";
      document.getElementById("squareFeetMin").value = "2500";
      document.getElementById("squareFeetMax").value = "3000";
      document.getElementById("inquiry").value = "We need 2500 to 3000 square feet in a high-footfall retail street. Our opening target is in 45 days. We can stretch to 3.2 lakh monthly if the fit and frontage are strong.";
      document.getElementById("missingFields").value = "";
      syncSegmentFields();
    }

    function syncSegmentFields() {
      const segment = segmentSelect.value;
      document.querySelectorAll(".residential-group").forEach((node) => node.classList.toggle("hidden", segment !== "residential"));
      document.querySelectorAll(".commercial-group").forEach((node) => node.classList.toggle("hidden", segment !== "commercial"));
      document.getElementById("propertyType").disabled = segment !== "residential";
      document.getElementById("businessType").disabled = segment !== "commercial";
      document.getElementById("squareFeetMin").disabled = segment !== "commercial";
      document.getElementById("squareFeetMax").disabled = segment !== "commercial";
      loadDefaultButton.textContent = segment === "commercial" ? "Load Residential Example" : "Load Whitefield Example";
    }

    function preferredVoice() {
      if (!playbackSupported) {
        return null;
      }
      const voices = window.speechSynthesis.getVoices();
      return voices.find((voice) => {
        const name = String(voice.name || "").toLowerCase();
        return name.includes("google") || name.includes("microsoft") || String(voice.lang || "").toLowerCase().startsWith("en");
      }) || voices[0] || null;
    }

    function speak(text, callbacks = {}) {
      if (!playbackSupported || !text) {
        if (callbacks.onend) callbacks.onend();
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = preferredVoice();
      utterance.rate = 0.98;
      utterance.pitch = 1;
      utterance.volume = 1;
      utterance.onend = () => {
        if (callbacks.onend) callbacks.onend();
      };
      utterance.onerror = () => {
        if (callbacks.onerror) callbacks.onerror();
        if (callbacks.onend) callbacks.onend();
      };
      window.speechSynthesis.speak(utterance);
    }

    function stopSpeechPlayback() {
      if (playbackSupported) {
        window.speechSynthesis.cancel();
      }
    }

    function playBeep(frequency = 880, durationMs = 140) {
      if (!AudioContextClass) return;
      try {
        const context = new AudioContextClass();
        const oscillator = context.createOscillator();
        const gainNode = context.createGain();
        oscillator.type = "sine";
        oscillator.frequency.value = frequency;
        gainNode.gain.setValueAtTime(0.001, context.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.001, context.currentTime + durationMs / 1000);
        oscillator.connect(gainNode);
        gainNode.connect(context.destination);
        oscillator.start();
        oscillator.stop(context.currentTime + durationMs / 1000);
        oscillator.onended = () => {
          context.close().catch(() => {});
        };
      } catch (error) {
        // Ignore audio context errors when browser blocks autoplay.
      }
    }

    function heardSkipIntent(text) {
      const normalized = String(text || "").trim().toLowerCase();
      return normalized === "skip" || normalized === "not required" || normalized.includes("skip") || normalized.includes("not required");
    }

    function cleanSpokenText(text) {
      return String(text || "")
        .replace(/\bdouble\b/gi, "2")
        .replace(/\btriple\b/gi, "3")
        .replace(/\bfour bedroom\b/gi, "4 bhk")
        .replace(/\bthree bedroom\b/gi, "3 bhk")
        .replace(/\btwo bedroom\b/gi, "2 bhk")
        .replace(/\bone bedroom\b/gi, "1 bhk")
        .replace(/\s+/g, " ")
        .trim();
    }

    function parseEmploymentType(text) {
      const normalized = cleanSpokenText(text).toLowerCase();
      if (normalized.includes("business")) return "business";
      if (normalized.includes("self")) return "self-employed";
      return "salaried";
    }

    function parseSegment(text) {
      const normalized = cleanSpokenText(text).toLowerCase();
      return normalized.includes("commercial") ? "commercial" : "residential";
    }

    function parseBudgetValue(text) {
      const normalized = cleanSpokenText(text).toLowerCase();
      const digits = normalized.replace(/[^0-9]/g, "");
      if (!digits) return "";
      const numeric = Number(digits);
      if (normalized.includes("crore")) return String(numeric * 10000000);
      if (normalized.includes("lakh") || normalized.includes("lakhs")) return String(numeric * 100000);
      return String(numeric);
    }

    function parseDaysValue(text) {
      const digits = cleanSpokenText(text).replace(/[^0-9]/g, "");
      return digits || "";
    }

    function parseSquareFeetValue(text) {
      const digits = cleanSpokenText(text).replace(/[^0-9]/g, "");
      return digits || "";
    }

    function inferLocation(text) {
      const normalized = cleanSpokenText(text);
      const knownLocations = [
        "Whitefield",
        "Marathahalli",
        "Sarjapur",
        "Indiranagar",
        "Koramangala",
        "HSR Layout",
        "Banashankari",
        "MG Road",
        "CBD Retail District",
      ];
      const matched = knownLocations.find((item) => normalized.toLowerCase().includes(item.toLowerCase()));
      if (matched) return matched;
      return normalized.replace(/^(in|at|from|near)\s+/i, "").trim();
    }

    function inferResidentialPropertyType(text) {
      const normalized = cleanSpokenText(text).toLowerCase();
      if (normalized.includes("4 bhk")) return "4BHK apartment";
      if (normalized.includes("3 bhk")) return "3BHK apartment";
      if (normalized.includes("2 bhk")) return "2BHK apartment";
      if (normalized.includes("1 bhk")) return "1BHK apartment";
      if (normalized.includes("villa")) return "villa";
      if (normalized.includes("plot")) return "plot";
      return cleanSpokenText(text);
    }

    function inferBusinessType(text) {
      const normalized = cleanSpokenText(text).toLowerCase();
      if (normalized.includes("cafe")) return "cafe";
      if (normalized.includes("restaurant")) return "restaurant";
      if (normalized.includes("office")) return "office";
      if (normalized.includes("retail")) return "retail";
      return cleanSpokenText(text);
    }

    function applyVoiceIntelligence() {
      const inquiry = cleanSpokenText(document.getElementById("inquiry").value);
      const segment = document.getElementById("segment").value;
      const locationInput = document.getElementById("location");
      const pickupInput = document.getElementById("customerLocation");
      const budgetInput = document.getElementById("budget");
      const timelineInput = document.getElementById("timelineDays");

      if (inquiry) {
        if (!locationInput.value.trim()) {
          const inferredLocation = inferLocation(inquiry);
          if (inferredLocation) {
            locationInput.value = inferredLocation;
          }
        }
        if (!budgetInput.value.trim()) {
          const inferredBudget = parseBudgetValue(inquiry);
          if (inferredBudget) {
            budgetInput.value = inferredBudget;
          }
        }
        if (!timelineInput.value.trim()) {
          const inferredTimeline = parseDaysValue(inquiry);
          if (inferredTimeline) {
            timelineInput.value = inferredTimeline;
          }
        }
        if (segment === "residential") {
          const propertyTypeInput = document.getElementById("propertyType");
          if (!propertyTypeInput.value.trim()) {
            propertyTypeInput.value = inferResidentialPropertyType(inquiry);
          }
          if (!pickupInput.value.trim() && inquiry.toLowerCase().includes("pickup")) {
            pickupInput.value = inferLocation(inquiry);
          }
        } else {
          const businessTypeInput = document.getElementById("businessType");
          if (!businessTypeInput.value.trim()) {
            businessTypeInput.value = inferBusinessType(inquiry);
          }
        }
      }
    }

    function waitForSpeech(promptText, options = {}) {
      if (!recognitionSupported) {
        return Promise.reject(new Error("Speech recognition is not supported in this browser."));
      }

      const {
        retries = 1,
        spokenPrompt = true,
        timeoutMs = 4500,
        allowSkip = false,
        emptyValue = "",
      } = options;

      voiceLog.textContent = promptText;

      return new Promise((resolve, reject) => {
        const recognition = new SpeechRecognition();
        recognition.lang = "en-US";
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.continuous = true;

        let settled = false;
        let recognitionTimeout = null;
        let finalTranscript = "";

        recognition.onresult = (event) => {
          let interimTranscript = "";
          for (let i = event.resultIndex; i < event.results.length; i += 1) {
            const transcript = event.results[i][0].transcript.trim();
            if (event.results[i].isFinal) {
              finalTranscript += ` ${transcript}`;
            } else {
              interimTranscript += ` ${transcript}`;
            }
          }
          const heard = (finalTranscript || interimTranscript).trim();
          if (heard) {
            voiceLog.textContent = `Heard: ${heard}`;
            if (allowSkip && heardSkipIntent(heard)) {
              settled = true;
              try {
                recognition.stop();
              } catch (error) {
                // ignore
              }
            }
          }
        };
        recognition.onerror = (event) => {
          settled = true;
          if (recognitionTimeout) clearTimeout(recognitionTimeout);
          const code = event.error || "speech_error";
          if ((code === "no-speech" || code === "audio-capture") && retries > 0) {
            voiceLog.textContent = "I did not catch that. Trying once more...";
            resolve(waitForSpeech(promptText, { retries: retries - 1, spokenPrompt, timeoutMs, allowSkip, emptyValue }));
            return;
          }
          if ((code === "no-speech" || code === "audio-capture") && allowSkip) {
            voiceLog.textContent = "No response captured. Marked as not required.";
            resolve(emptyValue);
            return;
          }
          reject(new Error(code));
        };
        recognition.onend = () => {
          recognitionBusy = false;
          const heard = finalTranscript.trim();
          if (allowSkip && heardSkipIntent(heard)) {
            settled = true;
            playBeep(740, 120);
            voiceLog.textContent = "Marked as not required.";
            resolve(emptyValue);
            return;
          }
          if (heard) {
            settled = true;
            playBeep(660, 120);
            voiceLog.textContent = `Heard: ${heard}`;
            resolve(heard);
            return;
          }
          if (!settled) {
            if (retries > 0) {
              voiceLog.textContent = "No speech captured. Trying again, please speak after the prompt.";
              resolve(waitForSpeech(promptText, { retries: retries - 1, spokenPrompt, timeoutMs, allowSkip, emptyValue }));
              return;
            }
            if (allowSkip) {
              voiceLog.textContent = "No response captured. Marked as not required.";
              resolve(emptyValue);
              return;
            }
            reject(new Error("no_speech_captured"));
          }
        };

        recognitionBusy = true;
        const startRecognition = () => {
          voiceLog.textContent = `${promptText} Listening now...`;
          window.setTimeout(() => {
            playBeep(900, 90);
            recognition.start();
          }, 80);
          recognitionTimeout = window.setTimeout(() => {
            try {
              recognition.stop();
            } catch (error) {
              // Ignore stop errors from already-ended sessions.
            }
          }, timeoutMs);
        };
        stopSpeechPlayback();
        if (spokenPrompt && promptText) {
          speak(promptText, { onend: startRecognition });
        } else {
          startRecognition();
        }
      });
    }

    async function startVoiceIntake() {
      if (!recognitionSupported) {
        voiceLog.textContent = "Voice intake needs a browser with speech recognition support.";
        return;
      }
      if (recognitionBusy) {
        voiceLog.textContent = "Voice assistant is already listening.";
        return;
      }

      try {
        stopSpeechPlayback();
        const name = await waitForSpeech("Tell me the customer name.", { retries: 0, timeoutMs: 4000 });
        document.getElementById("customerName").value = name;

        const employmentType = await waitForSpeech("Is the customer salaried, in business, or self-employed?", { retries: 0, timeoutMs: 4000 });
        document.getElementById("employmentType").value = parseEmploymentType(employmentType);

        const segmentAnswer = await waitForSpeech("Is this a residential or commercial lead?", { retries: 0, timeoutMs: 3500 });
        segmentSelect.value = parseSegment(segmentAnswer);
        syncSegmentFields();

        const location = await waitForSpeech("What is the preferred location?", { retries: 0, timeoutMs: 4000 });
        document.getElementById("location").value = inferLocation(location);

        const customerLocation = await waitForSpeech(
          "What is the customer's current pickup location? You can say skip or not required.",
          { retries: 0, timeoutMs: 5000, allowSkip: true, emptyValue: "" }
        );
        document.getElementById("customerLocation").value = heardSkipIntent(customerLocation) ? "" : inferLocation(customerLocation);

        const budget = await waitForSpeech("What is the budget?", { retries: 0, timeoutMs: 4000 });
        document.getElementById("budget").value = parseBudgetValue(budget);

        const timeline = await waitForSpeech("What is the timeline in days?", { retries: 0, timeoutMs: 3500 });
        document.getElementById("timelineDays").value = parseDaysValue(timeline);
        document.getElementById("profession").value = "";
        document.getElementById("totalExperienceYears").value = "";

        if (segmentSelect.value === "commercial") {
          const businessType = await waitForSpeech("What type of business is this lead for?", { retries: 0, timeoutMs: 4000 });
          document.getElementById("businessType").value = inferBusinessType(businessType);

          const sqftMin = await waitForSpeech("What is the minimum square footage required?", { retries: 0, timeoutMs: 3500 });
          document.getElementById("squareFeetMin").value = parseSquareFeetValue(sqftMin);

          const sqftMax = await waitForSpeech("What is the maximum square footage required?", { retries: 0, timeoutMs: 3500 });
          document.getElementById("squareFeetMax").value = parseSquareFeetValue(sqftMax);
        } else {
          const propertyType = await waitForSpeech("What property type does the customer want?", { retries: 0, timeoutMs: 4000 });
          document.getElementById("propertyType").value = inferResidentialPropertyType(propertyType);
        }

        const inquiry = await waitForSpeech("Now describe the inquiry in one sentence.", { retries: 0, timeoutMs: 5000 });
        document.getElementById("inquiry").value = cleanSpokenText(inquiry);
        applyVoiceIntelligence();
        document.getElementById("leadId").value = `voice_${segmentSelect.value}_${Date.now()}`;
        const finalMessage = "Thank you for the answers. I have captured the lead details and I am starting the workflow now.";
        voiceLog.textContent = finalMessage;
        playBeep(720, 150);
        await new Promise((resolve) => speak(finalMessage, { onend: resolve }));
        await runManualLead();
      } catch (error) {
        voiceLog.textContent = `Voice intake stopped: ${error.message}`;
      }
    }

    async function dictateInquiry() {
      if (!recognitionSupported) {
        voiceLog.textContent = "Voice dictation is not supported in this browser.";
        return;
      }
      if (recognitionBusy) {
        voiceLog.textContent = "Voice assistant is already listening.";
        return;
      }
      try {
        stopSpeechPlayback();
        const inquiry = await waitForSpeech("Please describe the customer inquiry.", { retries: 0, spokenPrompt: false, timeoutMs: 5000 });
        document.getElementById("inquiry").value = cleanSpokenText(inquiry);
        applyVoiceIntelligence();
        voiceLog.textContent = "Inquiry updated from voice input.";
      } catch (error) {
        voiceLog.textContent = `Dictation stopped: ${error.message}`;
      }
    }

    async function playLatestCall() {
      if (!playbackSupported) {
        voiceLog.textContent = "Speech playback is not supported in this browser.";
        return;
      }
      const response = await fetch("/calls/latest");
      const data = await response.json();
      if (!data.available || !data.call_transcript || !data.call_transcript.length) {
        voiceLog.textContent = "No call transcript is available yet. Run a lead through the workflow first.";
        return;
      }
      const script = data.call_transcript.map((turn) => `${turn.speaker}: ${turn.text}`).join(". ");
      voiceLog.textContent = `Playing latest call for ${data.customer_name}.`;
      speak(script);
    }

    async function consumeStream(response) {
      startButton.disabled = true;
      submitManualButton.disabled = true;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          addEventRow(event);

          if (event.event === "lead_received") {
            leads.set(event.lead_id, {
              customer_name: event.payload.customer_name,
              inquiry: event.payload.inquiry,
              stage: "received",
              segment: event.payload.segment || document.getElementById("segment").value
            });
            renderLeadCard(event.lead_id);
          }

          if (event.event === "lead_step") {
            const lead = leads.get(event.lead_id) || {};
            lead.grader_score = event.payload.grader_score;
            lead.stage = event.payload.last_action_result || lead.stage;
            if (event.payload.call_transcript && event.payload.call_transcript.length) {
              const customerTurns = event.payload.call_transcript.filter((turn) => turn.speaker === "customer");
              lead.last_contact_note = customerTurns.length ? customerTurns[customerTurns.length - 1].text : event.payload.call_outcome;
            }
            leads.set(event.lead_id, lead);
            renderLeadCard(event.lead_id);
            updateCabPanelFromPayload(event.payload, lead);
          }

          if (event.event === "lead_completed") {
            const lead = leads.get(event.lead_id) || {};
            lead.final_score = event.payload.final_score;
            lead.final_stage = event.payload.final_stage;
            leads.set(event.lead_id, lead);
            renderLeadCard(event.lead_id);
          }

          if (event.event === "run_completed") {
            statusText.textContent = `Completed ${event.payload.processed_leads} simulated leads.`;
          }
        }
      }

      startButton.disabled = false;
      submitManualButton.disabled = false;
    }

    async function startStream() {
      resetBoards();
      statusText.textContent = "Streaming default CRM traffic...";
      const response = await fetch("/simulate/live/stream?delay_seconds=0.35");
      await consumeStream(response);
    }

    async function runManualLead() {
      resetBoards();
      statusText.textContent = "Streaming manual lead...";
      const response = await fetch("/simulate/live/stream?delay_seconds=0.35", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(manualPayload())
      });
      await consumeStream(response);
    }

    startButton.addEventListener("click", startStream);
    submitManualButton.addEventListener("click", runManualLead);
    loadDefaultButton.addEventListener("click", loadWhitefieldExample);
    loadCommercialButton.addEventListener("click", loadCommercialExample);
    segmentSelect.addEventListener("change", syncSegmentFields);
    startVoiceIntakeButton.addEventListener("click", startVoiceIntake);
    dictateInquiryButton.addEventListener("click", dictateInquiry);
    playLatestCallButton.addEventListener("click", playLatestCall);
    if (!recognitionSupported && !playbackSupported) {
      voiceLog.textContent = "Voice features are unavailable in this browser. Use Chrome or Edge for speech recognition.";
    } else if (!recognitionSupported) {
      voiceLog.textContent = "Voice playback is available, but microphone dictation is not supported in this browser.";
    } else if (!playbackSupported) {
      voiceLog.textContent = "Voice dictation is available, but speech playback is not supported in this browser.";
    }
    loadWhitefieldExample();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/grader/{task_id}")
def grader(task_id: str) -> dict[str, object]:
    task = load_task(task_id)
    env.reset(task_id)
    current_state = env.state()
    return {"task_id": task_id, "score": grade_task(task, current_state)}
