from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from real_estate_pipeline import Action, RealEstatePipelineEnv
from real_estate_pipeline.graders import grade_task
from real_estate_pipeline.live_simulator import (
    DEFAULT_LIVE_LEADS,
    DEFAULT_STREAM_LEADS,
    simulate_live_traffic,
    stream_live_traffic_events,
)
from real_estate_pipeline.models import LiveTrafficSimulationRequest, LiveTrafficSimulationResponse
from real_estate_pipeline.tasks import load_task


app = FastAPI(title="Real Estate Pipeline OpenEnv", version="0.1.0")
env = RealEstatePipelineEnv()
latest_call_cache: dict[str, object] = {}


class ResetRequest(BaseModel):
    task_id: str | None = None


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
            Budget
            <input id="budget" type="number" value="9500000" />
          </label>
          <label>
            Timeline Days
            <input id="timelineDays" type="number" value="30" />
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
    const submitManualButton = document.getElementById("submitManualButton");
    const loadDefaultButton = document.getElementById("loadDefaultButton");
    const loadCommercialButton = document.getElementById("loadCommercialButton");
    const segmentSelect = document.getElementById("segment");
    const startVoiceIntakeButton = document.getElementById("startVoiceIntakeButton");
    const dictateInquiryButton = document.getElementById("dictateInquiryButton");
    const playLatestCallButton = document.getElementById("playLatestCallButton");
    const voiceLog = document.getElementById("voiceLog");
    const leads = new Map();
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
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

    function resetBoards() {
      leadList.innerHTML = "";
      eventList.innerHTML = "";
      leads.clear();
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
      document.getElementById("segment").value = "residential";
      document.getElementById("location").value = "Whitefield";
      document.getElementById("budget").value = "9500000";
      document.getElementById("timelineDays").value = "30";
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
      document.getElementById("segment").value = "commercial";
      document.getElementById("location").value = "CBD Retail District";
      document.getElementById("budget").value = "320000";
      document.getElementById("timelineDays").value = "45";
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

    function speak(text) {
      if (!playbackSupported) {
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1;
      utterance.pitch = 1;
      window.speechSynthesis.speak(utterance);
    }

    function waitForSpeech(promptText, retries = 2) {
      if (!recognitionSupported) {
        return Promise.reject(new Error("Speech recognition is not supported in this browser."));
      }

      voiceLog.textContent = promptText;
      if (playbackSupported) {
        speak(promptText);
      }

      return new Promise((resolve, reject) => {
        const recognition = new SpeechRecognition();
        recognition.lang = "en-US";
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.continuous = true;
        recognitionTimeout = null;

        let settled = false;
        let recognitionTimeout;
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
          }
        };
        recognition.onerror = (event) => {
          settled = true;
          if (recognitionTimeout) clearTimeout(recognitionTimeout);
          const code = event.error || "speech_error";
          if ((code === "no-speech" || code === "audio-capture") && retries > 0) {
            voiceLog.textContent = "I did not catch that. Trying once more...";
            resolve(waitForSpeech(promptText, retries - 1));
            return;
          }
          reject(new Error(code));
        };
        recognition.onend = () => {
          recognitionBusy = false;
          const heard = finalTranscript.trim();
          if (heard) {
            settled = true;
            resolve(heard);
            return;
          }
          if (!settled) {
            if (retries > 0) {
              voiceLog.textContent = "No speech captured. Trying again, please speak after the prompt.";
              resolve(waitForSpeech(promptText, retries - 1));
              return;
            }
            reject(new Error("no_speech_captured"));
          }
        };

        recognitionBusy = true;
        const startRecognition = () => {
          window.setTimeout(() => {
            recognition.start();
          }, 350);
          recognitionTimeout = window.setTimeout(() => {
            try {
              recognition.stop();
            } catch (error) {
              // Ignore stop errors from already-ended sessions.
            }
          }, 12000);
        };
        if (playbackSupported && promptText) {
          const utterance = new SpeechSynthesisUtterance(promptText);
          utterance.rate = 1;
          utterance.pitch = 1;
          utterance.onend = startRecognition;
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(utterance);
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
        const name = await waitForSpeech("Tell me the customer name.");
        document.getElementById("customerName").value = name;

        const segmentAnswer = (await waitForSpeech("Is this a residential or commercial lead?")).toLowerCase();
        if (segmentAnswer.includes("commercial")) {
          segmentSelect.value = "commercial";
          syncSegmentFields();
        } else {
          segmentSelect.value = "residential";
          syncSegmentFields();
        }

        const location = await waitForSpeech("What is the preferred location?");
        document.getElementById("location").value = location;

        const budget = await waitForSpeech("What is the budget?");
        document.getElementById("budget").value = budget.replace(/[^0-9]/g, "");

        const timeline = await waitForSpeech("What is the timeline in days?");
        document.getElementById("timelineDays").value = timeline.replace(/[^0-9]/g, "");

        if (segmentSelect.value === "commercial") {
          const businessType = await waitForSpeech("What type of business is this lead for?");
          document.getElementById("businessType").value = businessType;

          const sqftMin = await waitForSpeech("What is the minimum square footage required?");
          document.getElementById("squareFeetMin").value = sqftMin.replace(/[^0-9]/g, "");

          const sqftMax = await waitForSpeech("What is the maximum square footage required?");
          document.getElementById("squareFeetMax").value = sqftMax.replace(/[^0-9]/g, "");
        } else {
          const propertyType = await waitForSpeech("What property type does the customer want?");
          document.getElementById("propertyType").value = propertyType;
        }

        const inquiry = await waitForSpeech("Now describe the inquiry in one sentence.");
        document.getElementById("inquiry").value = inquiry;
        document.getElementById("leadId").value = `voice_${segmentSelect.value}_${Date.now()}`;
        voiceLog.textContent = "Voice intake completed. Review the form and run the lead.";
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
        voiceLog.textContent = "Listening for inquiry...";
        const inquiry = await waitForSpeech("");
        document.getElementById("inquiry").value = inquiry;
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
              stage: "received"
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
