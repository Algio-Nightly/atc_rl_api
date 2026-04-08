"""Departure rubric for ATC RL environment - takeoff and ground operations rewards."""

from typing import TYPE_CHECKING

from .base import BaseRubric

if TYPE_CHECKING:
    from rl_env.models import ATCAction, ATCObservation, AircraftObservation


class DepartureRubric(BaseRubric):
    """
    Departure rubric computing rewards for successful takeoffs,
    efficient taxi operations, and runway management.
    """

    REWARD_DEPARTURE_SUCCESS = 5.0
    REWARD_TAXI_STARTED = 1.0

    PENALTY_TAXI_DELAY = -0.5
    PENALTY_RUNWAY_OCCUPANCY = -0.3

    THRESHOLD_TAXI_TIME_MINUTES = 3.0

    def __init__(self, weight: float = 1.0):
        super().__init__(weight)
        self._prev_states: dict[str, str] = {}

    def forward(self, action: "ATCAction", observation: "ATCObservation") -> float:
        total_reward = 0.0

        aircraft_list = observation.aircraft

        for ac in aircraft_list:
            reward = self._compute_aircraft_departure(ac)
            total_reward += reward

        self._prev_states = {ac.callsign: ac.intent.state for ac in aircraft_list}

        return total_reward

    def _compute_aircraft_departure(self, ac: "AircraftObservation") -> float:
        reward = 0.0
        prev_state = self._prev_states.get(ac.callsign, "")
        current_state = ac.intent.state

        reward += self._check_departure_success(prev_state, current_state)
        reward += self._check_taxi_started(prev_state, current_state)
        reward += self._check_taxi_delay(ac)
        reward += self._check_runway_occupancy(ac)

        return reward

    def _check_departure_success(self, prev_state: str, current_state: str) -> float:
        if current_state == "CLIMB_OUT" and prev_state == "TAKEOFF_ROLL":
            return self.REWARD_DEPARTURE_SUCCESS
        return 0.0

    def _check_taxi_started(self, prev_state: str, current_state: str) -> float:
        if current_state == "TAXIING" and prev_state == "ON_GATE":
            return self.REWARD_TAXI_STARTED
        return 0.0

    def _check_taxi_delay(self, ac: "AircraftObservation") -> float:
        if ac.intent.state not in ("ON_GATE", "TAXIING", "HOLDING_SHORT"):
            return 0.0

        if ac.timing_stats is not None:
            taxi_time = ac.timing_stats.historical_times.get("TAXIING", 0.0)
            gate_time = ac.timing_stats.historical_times.get("ON_GATE", 0.0)
            total_ground_time = taxi_time + gate_time
            if total_ground_time > self.THRESHOLD_TAXI_TIME_MINUTES * 60:
                excess_minutes = (
                    total_ground_time - self.THRESHOLD_TAXI_TIME_MINUTES * 60
                ) / 60
                return self.PENALTY_TAXI_DELAY * excess_minutes

        return 0.0

    def _check_runway_occupancy(self, ac: "AircraftObservation") -> float:
        if ac.intent.state in ("LINE_UP", "TAKEOFF_ROLL"):
            return self.PENALTY_RUNWAY_OCCUPANCY
        return 0.0
