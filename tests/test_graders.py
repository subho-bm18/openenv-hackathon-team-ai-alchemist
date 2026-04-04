from real_estate_pipeline.env import RealEstatePipelineEnv


def test_all_tasks_produce_bounded_grader_scores() -> None:
    env = RealEstatePipelineEnv()
    for task_id in env.available_tasks():
        env.reset(task_id)
        score = env.state()["grader_score"]
        assert 0.0 <= score <= 1.0
