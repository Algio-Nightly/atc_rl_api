"""Safety rubric for ATC RL environment - collision and separation rewards."""

import math
from typing import TYPE_CHECKING

from .base import BaseRubric

if TYPE_CHECKING:
    from rl_env.models import ATCAction, ATCObservation, AircraftObservation


class SafetyRubric(BaseRubric):
    """
    Safety rubric computing rewards/penalties based on collision risk,
    separation violations, and runway incursions.
    """

    REWARD_LANDING_SUCCESS = 0.0

    PENALTY_COLLISION = -10.0
    PENALTY_RUNWAY_INCURSION = -10.0
    PENALTY_FUEL_EXHAUSTION = -10.0
    PENALTY_NEAR_MISS = -5.0
    PENALTY_SEPARATION_VIOLATION = -2.0
    PENALTY_CONFLICT_HIGH = -0.5
    PENALTY_CONFLICT_IMMINENT = -1.0

    THRESHOLD_NEAR_MISS_DIST_KM = 5.0
    THRESHOLD_NEAR_MISS_ALT_FT = 1000.0
    THRESHOLD_SEP_VIOLATION_DIST_KM = 5.0
    THRESHOLD_SEP_VIOLATION_ALT_FT = 1000.0

    def __init__(self, weight: float = 1.0):
        super().__init__(weight)
        self._prev_states: dict[str, str] = {}
        self._holding_start_times: dict[str, float] = {}

    def forward(self, action: "ATCAction", observation: "ATCObservation") -> float:
        total_reward = 0.0

        aircraft_list = observation.aircraft

        for ac in aircraft_list:
            reward = self._compute_aircraft_safety(ac, aircraft_list, observation)
            total_reward += reward

        self._prev_states = {ac.callsign: ac.intent.state for ac in aircraft_list}

        return total_reward

    def _compute_aircraft_safety(
        self,
        ac: "AircraftObservation",
        all_aircraft: list["AircraftObservation"],
        observation: "ATCObservation",
    ) -> float:
        reward = 0.0

        reward += self._check_collision_risk(ac, all_aircraft)

        reward += self._check_runway_incursion(ac, observation)

        reward += self._check_fuel_exhaustion(ac)

        reward += self._check_separation_violation(ac, all_aircraft)

        reward += self._check_conflict_risk(ac)

        return reward

    def _check_collision_risk(
        self, ac: "AircraftObservation", all_aircraft: list["AircraftObservation"]
    ) -> float:
        # Use engine's tracked minimum proximity when available
        if (
            ac.safety_metrics is not None
            and ac.safety_metrics.closest_proximity_km is not None
            and ac.safety_metrics.closest_proximity_km < 0.3
        ):
            return self.PENALTY_COLLISION

        for other in all_aircraft:
            if other.callsign == ac.callsign:
                continue

            dist_km = math.sqrt(
                (
                    ac.position.distance * self._segment_to_xy(ac.position.segment)[0]
                    - other.position.distance
                    * self._segment_to_xy(other.position.segment)[0]
                )
                ** 2
                + (
                    ac.position.distance * self._segment_to_xy(ac.position.segment)[1]
                    - other.position.distance
                    * self._segment_to_xy(other.position.segment)[1]
                )
                ** 2
            )

            alt_diff = abs(ac.position.altitude - other.position.altitude)

            if dist_km < 0.3 and alt_diff < 300:
                return self.PENALTY_COLLISION

            if (
                dist_km < self.THRESHOLD_NEAR_MISS_DIST_KM
                and alt_diff < self.THRESHOLD_NEAR_MISS_ALT_FT
            ):
                return self.PENALTY_NEAR_MISS

        return 0.0

    def _check_runway_incursion(
        self, ac: "AircraftObservation", observation: "ATCObservation"
    ) -> float:
        if ac.intent.state == "LANDING" and ac.intent.assigned_runway:
            runway_occupancy = observation.airport_status.runway_occupancy
            occupying = runway_occupancy.get(ac.intent.assigned_runway)
            if occupying and occupying != ac.callsign:
                return self.PENALTY_RUNWAY_INCURSION

        return 0.0

    def _check_fuel_exhaustion(self, ac: "AircraftObservation") -> float:
        if "low_fuel" in ac.alerts or "critical_emergency" in ac.alerts:
            return self.PENALTY_FUEL_EXHAUSTION
        return 0.0

    def _check_separation_violation(
        self, ac: "AircraftObservation", all_aircraft: list["AircraftObservation"]
    ) -> float:
        sep = ac.separation
        if sep.distance is None:
            return 0.0

        # Use engine's authoritative separation check when available
        if (
            ac.safety_metrics is not None
            and ac.safety_metrics.separation_warnings_triggered > 0
        ):
            return self.PENALTY_SEPARATION_VIOLATION

        if sep.closest_traffic:
            if sep.distance < self.THRESHOLD_SEP_VIOLATION_DIST_KM:
                alt_diff = 0.0
                for other in all_aircraft:
                    if other.callsign == sep.closest_traffic:
                        alt_diff = abs(ac.position.altitude - other.position.altitude)
                        break

                if alt_diff < self.THRESHOLD_SEP_VIOLATION_ALT_FT:
                    return self.PENALTY_SEPARATION_VIOLATION

        return 0.0

    def _check_conflict_risk(self, ac: "AircraftObservation") -> float:
        conflict_risk = ac.separation.conflict_risk
        if conflict_risk == "high":
            return self.PENALTY_CONFLICT_HIGH
        elif conflict_risk == "medium":
            pass
        return 0.0

    def _segment_to_xy(self, segment: str) -> tuple[float, float]:
        segment_angles = {
            "North": 0,
            "North-East": 45,
            "East": 90,
            "South-East": 135,
            "South": 180,
            "South-West": 225,
            "West": 270,
            "North-West": 315,
        }
        angle = math.radians(segment_angles.get(segment, 0))
        return (math.cos(angle), math.sin(angle))
