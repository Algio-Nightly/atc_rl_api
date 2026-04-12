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
    
    Implements dynamic redundancy penalties:
    - Diminishing rewards for repeated valid commands.
    - Increasing penalties for consecutive redundant or no-op commands.
    """

    REWARD_VALID_COMMAND = 0.1
    PENALTY_REDUNDANT_COMMAND_BASE = -0.05
    PENALTY_NO_OP_BASE = -0.1
    REWARD_GLIDE_SLOPE_COMPLIANCE = 0.2
    PENALTY_AIRSPACE_EXIT = -5.0
    PENALTY_COMMAND_REJECTED = -0.5

    # Patterns for basic format validation (removed deprecated VECTOR, APPROACH)
    COMMAND_PATTERNS = [
        r"ATC\s+ALTITUDE\s+[A-Z0-9]{2,10}\s+\d{1,5}$",
        r"ATC\s+SPEED\s+[A-Z0-9]{2,10}\s+\d{1,3}$",
        r"ATC\s+DIRECT\s+[A-Z0-9]{2,10}\s+(?:TO\s+)?[A-Z0-9_]{2,15}$",
        r"ATC\s+HOLD\s+[A-Z0-9]{2,10}(?:\s+[A-Z0-9_]{2,10})?(?:\s+\d{1,5})?$",
        r"ATC\s+LAND\s+[A-Z0-9]{2,10}\s+[A-Z0-9_]{2,10}$",
        r"ATC\s+RESUME\s+[A-Z0-9]{2,10}$",
        r"ATC\s+TAXI\s+[A-Z0-9]{2,10}\s+TO\s+[A-Z0-9_]{2,10}$",
        r"ATC\s+TAKEOFF\s+[A-Z0-9]{2,10}$",
        r"ATC\s+PASS$",
    ]

    def __init__(self, weight: float = 1.0):
        super().__init__(weight)
        self._prev_commands: dict[str, str] = {}
        self._command_counts: dict[str, dict[str, int]] = {}  # callsign -> {cmd_str: count}
        self._last_n_commands: dict[str, list[str]] = {}     # callsign -> [recent_cmds]
        self._in_airspace: dict[str, bool] = {}

    def forward(
        self,
        action: "ATCAction",
        observation: "ATCObservation",
        events: list[dict] | None = None,
    ) -> float:
        total_reward = 0.0

        # Create aircraft mapping for no-op checks
        ac_map = {ac.callsign: ac for ac in observation.aircraft}

        # 1. Command Validity & Redundancy
        total_reward += self._check_command_impact(action, ac_map)

        # 2. Command Rejections (authorized signal)
        total_reward += self._check_command_rejections(observation, events)

        # 3. Procedure Compliance
        total_reward += self._check_glide_slope_compliance(observation)

        # 4. Airspace Compliance
        total_reward += self._check_airspace_compliance(observation)

        # Update state for next step
        for cmd_str in action.commands:
            callsign_match = re.search(r"[A-Z0-9]{2,10}", cmd_str)
            if callsign_match:
                callsign = callsign_match.group()
                self._update_command_history(callsign, cmd_str)

        return total_reward

    def _update_command_history(self, callsign: str, cmd_str: str):
        """Update historical tracking for an aircraft."""
        if callsign not in self._command_counts:
            self._command_counts[callsign] = {}
            self._last_n_commands[callsign] = []

        # Update global frequency
        self._command_counts[callsign][cmd_str] = self._command_counts[callsign].get(cmd_str, 0) + 1
        
        # Update rolling window (last 5)
        history = self._last_n_commands[callsign]
        history.append(cmd_str)
        if len(history) > 5:
            history.pop(0)

    def _check_command_impact(self, action: "ATCAction", ac_map: dict[str, "AircraftObservation"]) -> float:
        if not action.commands:
            return 0.0

        step_reward = 0.0

        for cmd_str in action.commands:
            # Basic validation
            if not self._is_valid_command_format(cmd_str):
                continue

            # Special case: Global PASS is neutral (0 reward)
            if cmd_str.strip().upper() == "ATC PASS":
                continue

            callsign_match = re.search(r"[A-Z0-9]{2,10}", cmd_str)
            if not callsign_match:
                continue
            callsign = callsign_match.group()
            
            # Diminishing rewards logic
            counts = self._command_counts.get(callsign, {})
            freq = counts.get(cmd_str, 0)
            
            # Base valid command reward (diminishes with total frequency)
            validity_reward = max(0.01, self.REWARD_VALID_COMMAND - (freq * 0.02))
            step_reward += validity_reward

            # No-Op Check (High penalty if it changes nothing)
            if callsign in ac_map and self._is_no_op_command(cmd_str, ac_map[callsign]):
                # No-op penalty scales with how many times it's been done
                no_op_penalty = self.PENALTY_NO_OP_BASE * (1.2 ** freq)
                step_reward += no_op_penalty
                continue # Skip redundancy check if already penalized as no-op

            # Redundancy Check (Catch toggles and repeats)
            if self._is_redundant_in_history(callsign, cmd_str):
                # Redundancy penalty scales with frequency
                redundancy_penalty = self.PENALTY_REDUNDANT_COMMAND_BASE * (1.1 ** freq)
                step_reward += redundancy_penalty

        return step_reward

    def _is_valid_command_format(self, cmd: str) -> bool:
        cmd = cmd.strip()
        for pattern in self.COMMAND_PATTERNS:
            if re.match(pattern, cmd):
                return True
        return False

    def _is_no_op_command(self, cmd_str: str, ac: "AircraftObservation") -> bool:
        """Checks if the command would result in no change to the aircraft's targets."""
        parts = cmd_str.upper().split()
        if len(parts) < 3: return False
        
        command = parts[1]
        value = parts[-1] # Usually the last part is the value

        try:
            if command == "ALTITUDE":
                return abs(float(value) - ac.position.target_altitude) < 1.0
            if command == "SPEED":
                return abs(float(value) - ac.motion.target_speed) < 1.0
            if command == "HOLD" and ac.intent.state == "HOLDING":
                return True
            if command == "LAND" and ac.intent.state == "ENROUTE_CLEARED":
                return True
            if command == "RESUME" and ac.intent.assigned_runway is None and ac.intent.next_waypoint:
                # If already correctly following STAR and no override exists
                # (Simple heuristic: check if targets match current STAR targets)
                return False 
        except (ValueError, IndexError):
            pass
            
        return False

    def _is_redundant_in_history(self, callsign: str, cmd_str: str) -> bool:
        """Checks if the command has appeared recently or frequently."""
        history = self._last_n_commands.get(callsign, [])
        if not history:
            return False
            
        # Immediate repeat
        if cmd_str == history[-1]:
            return True
            
        # Catch toggle loops (e.g. A B A)
        if len(history) >= 2 and cmd_str == history[-2]:
            return True
            
        return False

    def _check_command_rejections(
        self, observation: "ATCObservation", events: list[dict] | None = None
    ) -> float:
        penalty = 0.0
        if events:
            for event in events:
                if event.get("type") == "COMMAND_ERROR" and event.get("callsign"):
                    penalty += self.PENALTY_COMMAND_REJECTED

        for ac in observation.aircraft:
            if ac.command_rejections:
                penalty += self.PENALTY_COMMAND_REJECTED * len(ac.command_rejections)

        return penalty

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
