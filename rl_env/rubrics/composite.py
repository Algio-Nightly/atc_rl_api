"""Composite ATCRubric - weighted sum of all rubric components."""

from typing import TYPE_CHECKING

from .base import BaseRubric, WeightedSum
from .safety import SafetyRubric
from .efficiency import EfficiencyRubric
from .compliance import ComplianceRubric
from .departure import DepartureRubric

if TYPE_CHECKING:
    from rl_env.models import ATCAction, ATCObservation


class ATCRubric(WeightedSum):
    """
    Composite rubric combining Safety, Efficiency, Compliance, Format, and Departure rubrics.

    Default weights:
        - Safety: 35%
        - Efficiency: 30%
        - Compliance: 15%
        - Format: 5%
        - Departure: 15%
    """

    DEFAULT_WEIGHTS = {
        "safety": 0.35,
        "efficiency": 0.30,
        "compliance": 0.15,
        "format": 0.05,
        "departure": 0.15,
    }

    def __init__(
        self,
        safety_weight: float = DEFAULT_WEIGHTS["safety"],
        efficiency_weight: float = DEFAULT_WEIGHTS["efficiency"],
        compliance_weight: float = DEFAULT_WEIGHTS["compliance"],
        format_weight: float = DEFAULT_WEIGHTS["format"],
        departure_weight: float = DEFAULT_WEIGHTS["departure"],
    ):
        super().__init__()

        self.safety = SafetyRubric(weight=safety_weight)
        self.efficiency = EfficiencyRubric(weight=efficiency_weight)
        self.compliance = ComplianceRubric(weight=compliance_weight)
        self.format = FormatRubric(weight=format_weight)
        self.departure = DepartureRubric(weight=departure_weight)

        self._rubrics = [
            self.safety,
            self.efficiency,
            self.compliance,
            self.format,
            self.departure,
        ]

    def forward(
        self,
        action: "ATCAction",
        observation: "ATCObservation",
        events: list[dict] | None = None,
    ) -> float:
        self._last_rewards = {}

        safety_reward = self.safety.forward(action, observation, events=events)
        self._last_rewards["safety"] = safety_reward

        efficiency_reward = self.efficiency.forward(action, observation, events=events)
        self._last_rewards["efficiency"] = efficiency_reward

        compliance_reward = self.compliance.forward(action, observation, events=events)
        self._last_rewards["compliance"] = compliance_reward

        format_reward = self.format.forward(action, observation, events=events)
        self._last_rewards["format"] = format_reward

        departure_reward = self.departure.forward(action, observation, events=events)
        self._last_rewards["departure"] = departure_reward

        total = (
            safety_reward * self.safety.weight
            + efficiency_reward * self.efficiency.weight
            + compliance_reward * self.compliance.weight
            + format_reward * self.format.weight
            + departure_reward * self.departure.weight
        )
        return total


class FormatRubric(BaseRubric):
    """
    Format rubric computing rewards for proper action format and structure.
    """

    REWARD_WELL_FORMED = 0.05
    PENALTY_MALFORMED = -0.1

    def forward(
        self,
        action: "ATCAction",
        observation: "ATCObservation",
        events: list[dict] | None = None,
    ) -> float:
        if not action.commands:
            return 0.0

        reward = 0.0

        for cmd in action.commands:
            if self._is_well_formed(cmd):
                reward += self.REWARD_WELL_FORMED
            else:
                reward += self.PENALTY_MALFORMED

        return reward

    def _is_well_formed(self, cmd: str) -> bool:
        if not cmd or not isinstance(cmd, str):
            return False

        cmd = cmd.strip()
        if not cmd.startswith("ATC "):
            return False

        if len(cmd) < 10 or len(cmd) > 100:
            return False

        return True
