from real_estate_pipeline.env import RealEstatePipelineEnv
from real_estate_pipeline.models import Action


def test_reset_returns_initial_observation() -> None:
    env = RealEstatePipelineEnv()
    observation = env.reset("residential_buyer_qualification")
    assert observation.task_id == "residential_buyer_qualification"
    assert observation.step_count == 0


def test_step_updates_state() -> None:
    env = RealEstatePipelineEnv()
    env.reset("residential_buyer_qualification")
    result = env.step(
        Action(
            action_type="classify_opportunity",
            opportunity_id="opp_res_001",
            category="residential_buyer",
        )
    )
    assert result.observation.active_opportunity.category == "residential_buyer"
    assert result.reward.value > 0


def test_call_customer_and_builder_appointment_update_state() -> None:
    env = RealEstatePipelineEnv()
    env.reset("residential_buyer_qualification")
    env.step(Action(action_type="classify_opportunity", opportunity_id="opp_res_001", category="residential_buyer"))
    env.step(Action(action_type="set_priority", opportunity_id="opp_res_001", priority="high"))
    env.step(Action(action_type="recommend_property", opportunity_id="opp_res_001", property_id="res_prop_101"))

    contact_result = env.step(
        Action(
            action_type="call_customer",
            opportunity_id="opp_res_001",
            message="Called the buyer to confirm interest and site-visit readiness.",
        )
    )
    assert contact_result.observation.active_opportunity.customer_contacted is True
    assert contact_result.observation.active_opportunity.last_contact_note is not None
    assert len(contact_result.observation.active_opportunity.call_transcript) >= 3
    assert contact_result.observation.active_opportunity.call_outcome is not None

    appointment_result = env.step(
        Action(
            action_type="schedule_builder_appointment",
            opportunity_id="opp_res_001",
            property_id="res_prop_101",
            appointment_party="builder",
        )
    )
    assert appointment_result.observation.active_opportunity.appointment_type == "builder_appointment"
    assert appointment_result.observation.active_opportunity.stage == "builder_appointment_scheduled"
