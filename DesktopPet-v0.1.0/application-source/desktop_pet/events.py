from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PetEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


BEHAVIOR_EVENTS = {"idle", "hover", "click", "drag_start", "drag_end"}
USAGE_EVENTS = {"usage_normal", "usage_low", "usage_critical"}


def usage_state(remaining: float) -> str:
    if remaining > 50:
        return "usage_normal"
    if remaining >= 20:
        return "usage_low"
    return "usage_critical"
