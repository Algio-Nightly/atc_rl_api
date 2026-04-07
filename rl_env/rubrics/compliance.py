"""Compliance rubric for ATC RL environment - command validity and airspace compliance."""

import re
from typing import TYPE_CHECKING

from .base import BaseRubric

if TYPE_CHECKING:
    from rl_env.models import ATCAction, ATCObservation, AircraftObservation


class ComplianceRubric(BaseRubric):
    """
    Compliance rubric computing rewards based on valid command usage,
    airspace regulations, and proper procedure adherence.
    """

    REWARD_VALID_COMMAND = 0.1
    PENALTY_REDUNDANT_COMMAND = -0.05
    REWARD_GLIDE_SLOPE_COMPLIANCE = 0.2
    PENALTY_AIRSPACE_EXIT = -5.0

    COMMAND_PATTERNS = [
        r"ATC\s+VECTOR\s+[A-Z]{3}\d{1,4}\s+\d{1,3}$",
        r"ATC\s+ALTITUDE\s+[A-Z]{3}\d{1,4}\s+\d{1,5}$",
        r"ATC\s+SPEED\s+[A-Z]{3}\d{1,4}\s+\d{1,3}$",
        r"ATC\s+DIRECT\s+[A-Z]{3}\d{1,4}\s+[A-Z]{2,5}$",
        r"ATC\s+HOLD\s+[A-Z]{3}\d{1,4}\s+[A-Z]{2,5}\s+\d{1,5}$",
        r"ATC\s+APPROACH\s+[A-Z]{3}\d{1,4}$",
        r"ATC\s+LAND\s+[A-Z]{3}\d{1,4}\s+[A-Z]{2}\d[LRC]?$",
        r"ATC\s+RESUME\s+[A-Z]{3}\d{1,4}$",
        r"ATC\s+CLEARED\s+[A-Z]{3}\d{1,4}\s+[A-Z]+$",
    ]

    def __init__(self, weight: float = 1.0):
        super().__init__(weight)
        self._prev_commands: dict[str, str] = {}
        self._prev_altitudes: dict[str, int] = {}
        self._in_airspace: dict[str, bool] = {}

    def forward(self, action: "ATCAction", observation: "ATCObservation") -> float:
        total_reward = 0.0

        total_reward += self._check_command_validity(action)

        total_reward += self._check_glide_slope_compliance(observation)

        total_reward += self._check_airspace_compliance(observation)

        for cmd in action.commands:
            callsign_match = re.search(r"[A-Z]{3}\d{1,4}", cmd)
            if callsign_match:
                callsign = callsign_match.group()
                self._prev_commands[callsign] = cmd

        for ac in observation.aircraft:
            self._prev_altitudes[ac.callsign] = ac.position.altitude
            self._in_airspace[ac.callsign] = True

        return total_reward

    def _check_command_validity(self, action: "ATCAction") -> float:
        if not action.commands:
            return 0.0

        reward = 0.0

        for cmd in action.commands:
            if self._is_valid_command_format(cmd):
                reward += self.REWARD_VALID_COMMAND

                if self._is_redundant_command(cmd):
                    reward += self.PENALTY_REDUNDANT_COMMAND
            else:
                pass

        return reward

    def _is_valid_command_format(self, cmd: str) -> bool:
        cmd = cmd.strip()
        for pattern in self.COMMAND_PATTERNS:
            if re.match(pattern, cmd):
                return True
        return False

    def _is_redundant_command(self, cmd: str) -> bool:
        callsign_match = re.search(r"[A-Z]{3}\d{1,4}", cmd)
        if not callsign_match:
            return False

        callsign = callsign_match.group()
        prev_cmd = self._prev_commands.get(callsign, "")

        if not prev_cmd:
            return False

        cmd_type_match = re.match(r"ATC\s+(\w+)", cmd)
        prev_cmd_type_match = re.match(r"ATC\s+(\w+)", prev_cmd)

        if not cmd_type_match or not prev_cmd_type_match:
            return False

        if cmd_type_match.group(1) != prev_cmd_type_match.group(1):
            return False

        cmd_rest = cmd[len(cmd_type_match.group(0)) :].strip()
        prev_rest = prev_cmd[len(prev_cmd_type_match.group(0)) :].strip()

        return cmd_rest == prev_rest

    def _check_glide_slope_compliance(self, observation: "ATCObservation") -> float:
        reward = 0.0

        for ac in observation.aircraft:
            if ac.intent.state == "APPROACH":
                if 100 <= ac.position.altitude <= 3000:
                    target_alt = ac.position.target_altitude
                    alt_diff = abs(ac.position.altitude - target_alt)

                    if alt_diff < 500:
                        reward += self.REWARD_GLIDE_SLOPE_COMPLIANCE

        return reward

    def _check_airspace_compliance(self, observation: "ATCObservation") -> float:
        penalty = 0.0

        for ac in observation.aircraft:
            if ac.position.altitude > 45000:
                penalty += self.PENALTY_AIRSPACE_EXIT
            if ac.position.altitude < 0:
                penalty += self.PENALTY_AIRSPACE_EXIT

        return penalty
