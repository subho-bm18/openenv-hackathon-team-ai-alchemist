from real_estate_pipeline.live_simulator import DEFAULT_INVENTORY, DEFAULT_LIVE_LEADS
from real_estate_pipeline.policy import best_property_match, choose_priority, property_fit_score
from real_estate_pipeline.tasks import list_eval_task_ids
from real_estate_pipeline.training_data import build_step_training_records, build_task_training_records, generate_synthetic_leads


def test_choose_priority_marks_high_intent_whitefield_lead_high() -> None:
    lead = DEFAULT_LIVE_LEADS[0]
    assert choose_priority(lead) == "high"


def test_property_fit_score_prefers_whitefield_2bhk_match() -> None:
    lead = DEFAULT_LIVE_LEADS[0]
    whitefield_fit = property_fit_score(lead, DEFAULT_INVENTORY[0])
    sarjapur_fit = property_fit_score(lead, DEFAULT_INVENTORY[1])

    assert whitefield_fit > sarjapur_fit
    matched = best_property_match(lead, [])
    assert matched is None


def test_training_data_contains_fixture_and_simulated_records() -> None:
    records = build_task_training_records()

    assert len(records) >= 100
    sources = {record["source"] for record in records}
    assert "fixture" in sources
    assert "simulated_live" in sources
    assert "eval_fixture" in sources
    assert any(record["target"]["property_id"] == "res_prop_101" for record in records)


def test_generate_synthetic_leads_produces_large_pool() -> None:
    leads = generate_synthetic_leads()

    assert len(leads) == 120
    assert any(lead.segment == "commercial" for lead in leads)
    assert any(lead.segment == "residential" for lead in leads)


def test_step_training_records_include_next_action_targets() -> None:
    records = build_step_training_records()

    assert len(records) > 200
    assert records[0]["record_type"] == "step"
    assert "action_type" in records[0]["target"]


def test_eval_fixtures_are_available() -> None:
    eval_ids = list_eval_task_ids()

    assert "residential_noisy_whatsapp_style" in eval_ids
    assert "commercial_budget_stretch" in eval_ids
