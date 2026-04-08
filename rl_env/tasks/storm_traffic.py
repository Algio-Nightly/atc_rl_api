"""StormTraffic task - Hard task with 10 aircraft, wind changes, and emergencies."""

import math
import random
from typing import TYPE_CHECKING

from .base import Task

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class StormTrafficTask(Task):
    """
    Hard task: 10 aircraft, wind changes, emergency handling.

    Scenario: Ten aircraft in challenging conditions with dynamic weather
    and emergency situations. Some aircraft have low fuel requiring
    priority handling. Agent must manage all traffic safely while
    dealing with changing wind conditions.

    Scoring:
        - 0.3 for completion rate
        - 0.2 for safety
        - 0.1 for efficiency
        - 0.3 for emergency handling
        - 0.1 for fuel management
    """

    WIND_CHANGE_MIN_INTERVAL = 60.0
    WIND_CHANGE_MAX_INTERVAL = 120.0
    INITIAL_FUEL_EMERGENCY_AIRCRAFT = [0, 1, 2]

    def __init__(self):
        self._last_wind_change_time = 0.0
        self._next_wind_change_interval = 0.0
        self._emergency_landed_count = 0
        self._emergency_total = 3

    def setup(self, env: "ATCEnv") -> None:
        """Configure environment for storm traffic task."""
        env.reset(task="storm_traffic", skip_spawn=True)
        self._last_wind_change_time = 0.0
        self._next_wind_change_interval = self._get_next_wind_change_interval()
        self._emergency_landed_count = 0
        upwind_gates = env._select_upwind_gates()
        gates = upwind_gates if upwind_gates else ["N", "S", "E", "W"]
        ac_types = ["B737", "A320", "B777", "E190", "A350"]
        weight_classes = ["Heavy", "Medium", "Light", "Heavy", "Medium"]
        for i in range(10):
            gate = gates[i % len(gates)]
            ac_type = ac_types[i % len(ac_types)]
            weight_class = weight_classes[i % len(weight_classes)]
            env.engine.add_aircraft(
                callsign=f"RL{i + 1:03d}",
                ac_type=ac_type,
                weight_class=weight_class,
                gate=gate,
                altitude=min(8000 + i * 1000, 15000),
                heading=None,
                speed=250,
            )
        self._setup_emergency_aircraft(env)
        env._initial_aircraft_count = len(env.engine.aircrafts)
        env._previous_observation = env._build_observation()

    def _get_next_wind_change_interval(self) -> float:
        """Get random interval until next wind change."""
        return random.uniform(
            self.WIND_CHANGE_MIN_INTERVAL, self.WIND_CHANGE_MAX_INTERVAL
        )

    def _setup_emergency_aircraft(self, env: "ATCEnv") -> None:
        """Setup low fuel emergency aircraft."""
        assert env.engine is not None
        for i in self.INITIAL_FUEL_EMERGENCY_AIRCRAFT:
            if i < len(list(env.engine.aircrafts.keys())):
                callsign = list(env.engine.aircrafts.keys())[i]
                if callsign in env.engine.aircrafts:
                    ac = env.engine.aircrafts[callsign]
                    ac.fuel_level = 5.0
                    ac.emergency_index = 1

    def grade(self, env: "ATCEnv") -> float:
        """
        Calculate score for storm traffic task.

        Returns:
            Score between 0.0 and 1.0
        """
        completion_score = self._grade_completion(env)
        safety_score = self._grade_safety(env)
        efficiency_score = self._grade_efficiency(env)
        emergency_score = self._grade_emergency_handling(env)
        fuel_score = self._grade_fuel_management(env)

        total = (
            completion_score
            + safety_score
            + efficiency_score
            + emergency_score
            + fuel_score
        )
        return max(0.0, min(1.0, total))

    def _grade_completion(self, env: "ATCEnv") -> float:
        """Grade based on how many aircraft landed safely."""
        assert env.engine is not None
        initial_count = (
            env._initial_aircraft_count
            if hasattr(env, "_initial_aircraft_count")
            else 10
        )
        if initial_count == 0:
            return 0.0

        landed_count = 0
        for ac in env.engine.aircrafts.values():
            if ac.state in ("LANDING", "TAXIING"):
                landed_count += 1

        completion_rate = landed_count / initial_count
        return 0.3 * completion_rate

    def _grade_safety(self, env: "ATCEnv") -> float:
        """Grade based on safety record."""
        if self._has_collision(env):
            return 0.0
        if self._has_separation_violation(env):
            return 0.1
        return 0.2

    def _grade_efficiency(self, env: "ATCEnv") -> float:
        """Grade based on efficiency."""
        sim_time = env.engine.simulation_time if env.engine else 0.0
        initial_count = (
            env._initial_aircraft_count
            if hasattr(env, "_initial_aircraft_count")
            else 10
        )

        if initial_count == 0:
            return 0.0

        expected_time = 200.0 + (initial_count - 1) * 50.0
        if sim_time <= expected_time:
            return 0.1
        else:
            time_ratio = max(0.0, 1.0 - (sim_time - expected_time) / expected_time)
            return 0.1 * time_ratio

    def _grade_emergency_handling(self, env: "ATCEnv") -> float:
        """Grade based on emergency handling."""
        assert env.engine is not None
        emergency_aircraft = self.INITIAL_FUEL_EMERGENCY_AIRCRAFT
        emergency_landed = 0

        callsigns = list(env.engine.aircrafts.keys())
        for i in emergency_aircraft:
            if i < len(callsigns):
                callsign = callsigns[i]
                if callsign in env.engine.aircrafts:
                    ac = env.engine.aircrafts[callsign]
                    if ac.state in ("LANDING", "TAXIING"):
                        emergency_landed += 1

        if len(emergency_aircraft) == 0:
            return 0.3

        emergency_rate = emergency_landed / len(emergency_aircraft)
        return 0.3 * emergency_rate

    def _grade_fuel_management(self, env: "ATCEnv") -> float:
        """Grade based on fuel management."""
        assert env.engine is not None
        crashed_fuel = 0
        for ac in env.engine.aircrafts.values():
            if hasattr(ac, "fuel_level") and ac.fuel_level <= 0:
                crashed_fuel += 1

        total_aircraft = len(env.engine.aircrafts)
        if total_aircraft == 0:
            return 0.1

        fuel_score = 1.0 - (crashed_fuel / total_aircraft)
        return 0.1 * fuel_score

    def is_complete(self, env: "ATCEnv") -> bool:
        """Check if episode should end."""
        if env.engine is None:
            return False

        if env.engine.is_terminal:
            return True

        if self._all_handled(env):
            return True

        if self._has_collision(env):
            return True

        if self._time_exceeded(env):
            return True

        return False

    def _all_handled(self, env: "ATCEnv") -> bool:
        """Check if all aircraft have been handled (landed or exited)."""
        assert env.engine is not None
        if not env.engine.aircrafts:
            return True

        for ac in env.engine.aircrafts.values():
            if ac.state not in ("LANDING", "TAXIING", "CRASHED"):
                if ac.altitude > 500:
                    return False
        return True

    def _has_collision(self, env: "ATCEnv") -> bool:
        """Check if collision occurred."""
        assert env.engine is not None
        for event in env.engine.event_buffer:
            if event.get("type") == "CRASH":
                return True
        return False

    def _has_separation_violation(self, env: "ATCEnv") -> bool:
        """Check if separation violation occurred."""
        assert env.engine is not None
        for event in env.engine.event_buffer:
            if event.get("type") == "SEPARATION_VIOLATION":
                return True
        return False

    def _time_exceeded(self, env: "ATCEnv") -> bool:
        """Check if maximum time exceeded."""
        assert env.engine is not None
        max_time = 1200.0
        return env.engine.simulation_time >= max_time

    def update_wind(self, env: "ATCEnv") -> None:
        """Update wind conditions if interval has passed."""
        if env.engine is None:
            return

        current_time = env.engine.simulation_time
        if (
            current_time - self._last_wind_change_time
            >= self._next_wind_change_interval
        ):
            self._change_wind(env)
            self._last_wind_change_time = current_time
            self._next_wind_change_interval = self._get_next_wind_change_interval()

    def _change_wind(self, env: "ATCEnv") -> None:
        """Change wind conditions randomly."""
        assert env.engine is not None
        import random

        env.engine.wind_heading = random.randint(0, 359)
        env.engine.wind_speed = random.randint(5, 30)

    @property
    def difficulty(self) -> str:
        """Return difficulty level."""
        return "hard"
