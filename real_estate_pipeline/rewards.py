from __future__ import annotations

from .models import Action, Reward


def base_step_penalty() -> Reward:
    return Reward(value=-0.02, components={"step_penalty": -0.02}, penalties=["extra_step"])


def apply_delta(
    reward: Reward,
    name: str,
    value: float,
    signal: str | None = None,
    penalty: str | None = None,
) -> Reward:
    reward.value += value
    reward.components[name] = reward.components.get(name, 0.0) + value
    if signal:
        reward.progress_signals.append(signal)
    if penalty:
        reward.penalties.append(penalty)
    return reward


def invalid_action_reward(action: Action, message: str) -> Reward:
    reward = base_step_penalty()
    return apply_delta(
        reward,
        f"invalid_{action.action_type}",
        -0.10,
        penalty=message,
    )
