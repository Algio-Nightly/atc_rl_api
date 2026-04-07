"""Efficiency rubric for ATC RL environment - landing, time, and fuel rewards."""

from typing import TYPE_CHECKING

from .base import BaseRubric

if TYPE_CHECKING:
    from rl_env.models import ATCAction, ATCObservation, AircraftObservation


class EfficiencyRubric(BaseRubric):
    """
    Efficiency rubric computing rewards based on successful operations,
    timely performance, and fuel consumption.
    """

    REWARD_LANDING_SUCCESS = 5.0
    REWARD_STAR_COMPLETION = 2.0
    REWARD_WAYPOINT_REACHED = 0.5

    PENALTY_GO_AROUND = -3.0
    PENALTY_TIME_PER_AIRCRAFT_PER_STEP = -0.01
    PENALTY_FUEL_PER_PERCENT_CONSUMED = -0.1
    PENALTY_HOLDING_PER_MINUTE = -0.5

    THRESHOLD_HOLDING_TIME_MINUTES = 5.0

    def __init__(self, weight: float = 1.0):
        super().__init__(weight)
        self._prev_states: dict[str, str] = {}
        self._prev_waypoints: dict[str, str] = {}
        self._holding_start_times: dict[str, float] = {}

    def forward(self, action: "ATCAction", observation: "ATCObservation") -> float:
        total_reward = 0.0

        aircraft_list = observation.aircraft
        sim_time = observation.metrics.simulation_time

        for ac in aircraft_list:
            reward = self._compute_aircraft_efficiency(
                ac, aircraft_list, observation, sim_time
            )
            total_reward += reward

        num_aircraft = len(aircraft_list)
        if num_aircraft > 0:
            total_reward += self.PENALTY_TIME_PER_AIRCRAFT_PER_STEP * num_aircraft

        self._prev_states = {ac.callsign: ac.intent.state for ac in aircraft_list}
        self._prev_waypoints = {
            ac.callsign: ac.intent.next_waypoint for ac in aircraft_list
        }

        return total_reward

    def _compute_aircraft_efficiency(
        self,
        ac: "AircraftObservation",
        all_aircraft: list["AircraftObservation"],
        observation: "ATCObservation",
        sim_time: float,
    ) -> float:
        reward = 0.0

        reward += self._check_landing_success(ac)

        reward += self._check_star_completion(ac)

        reward += self._check_waypoint_reached(ac)

        reward += self._check_go_around(ac)

        reward += self._check_fuel_penalty(ac)

        reward += self._check_holding_penalty(ac, sim_time)

        return reward

    def _check_landing_success(self, ac: "AircraftObservation") -> float:
        prev_state = self._prev_states.get(ac.callsign, "")
        if ac.intent.state == "LANDING" and prev_state == "APPROACH":
            if ac.position.altitude < 100 and ac.position.distance < 0.2:
                return self.REWARD_LANDING_SUCCESS
        return 0.0

    def _check_star_completion(self, ac: "AircraftObservation") -> float:
        if (
            ac.intent.next_waypoint == "CLEARED_ILS"
            or ac.intent.next_waypoint == "RUNWAY"
        ):
            prev_wp = self._prev_waypoints.get(ac.callsign, "")
            if prev_wp and prev_wp != ac.intent.next_waypoint:
                if "STAR" in prev_wp.upper() or "IAF" in prev_wp.upper():
                    return self.REWARD_STAR_COMPLETION
        return 0.0

    def _check_waypoint_reached(self, ac: "AircraftObservation") -> float:
        prev_wp = self._prev_waypoints.get(ac.callsign, "")
        if prev_wp and ac.intent.next_waypoint != prev_wp:
            if not any(
                x in ac.intent.next_waypoint.upper()
                for x in ["STAR", "ILS", "RUNWAY", "APPROACH"]
            ):
                return self.REWARD_WAYPOINT_REACHED
        return 0.0

    def _check_go_around(self, ac: "AircraftObservation") -> float:
        prev_state = self._prev_states.get(ac.callsign, "")
        if ac.intent.state == "GO_AROUND" and prev_state in ["APPROACH", "LANDING"]:
            return self.PENALTY_GO_AROUND
        return 0.0

    def _check_fuel_penalty(self, ac: "AircraftObservation") -> float:
        return 0.0

    def _check_holding_penalty(
        self, ac: "AircraftObservation", sim_time: float
    ) -> float:
        if ac.intent.state == "HOLDING":
            if ac.callsign not in self._holding_start_times:
                self._holding_start_times[ac.callsign] = sim_time
            else:
                holding_duration = sim_time - self._holding_start_times[ac.callsign]
                if holding_duration > self.THRESHOLD_HOLDING_TIME_MINUTES * 60:
                    excess_minutes = (
                        holding_duration - self.THRESHOLD_HOLDING_TIME_MINUTES * 60
                    ) / 60
                    return self.PENALTY_HOLDING_PER_MINUTE * excess_minutes
        else:
            if ac.callsign in self._holding_start_times:
                del self._holding_start_times[ac.callsign]
        return 0.0
