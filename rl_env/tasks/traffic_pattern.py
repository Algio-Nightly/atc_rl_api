"""TrafficPattern task - Medium task with 4 aircraft separation management."""

import math
from typing import TYPE_CHECKING

from .base import Task

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class TrafficPatternTask(Task):
    """
    Medium task: 4 aircraft, separation management.

    Scenario: Four aircraft approach from different directions.
    The agent must sequence them for landing while maintaining
    separation standards and avoiding runway incursions.

    Scoring:
        - 0.4 for all landed
        - 0.3 for no collisions
        - 0.2 for no runway incursions
        - 0.1 for avg time < threshold
    """

    AVG_TIME_THRESHOLD_SECONDS = 400.0

    def setup(self, env: "ATCEnv") -> None:
        """Configure environment for traffic pattern task."""
        env.reset(task="traffic_pattern", skip_spawn=True)
        upwind_gates = env._select_upwind_gates()
        gates = (
            [g for g in ["N", "S", "E", "W"] if g in upwind_gates]
            if upwind_gates
            else ["N", "S", "E", "W"]
        )
        if len(gates) < 4:
            gates = (gates * 4)[:4]
        ac_types = ["B737", "A320", "B777", "E190"]
        weight_classes = ["Heavy", "Medium", "Light"]
        for i in range(4):
            gate = gates[i % len(gates)]
            env.engine.add_aircraft(
                callsign=f"RL{i + 1:03d}",
                ac_type=ac_types[i],
                weight_class=weight_classes[i],
                gate=gate,
                altitude=8000 + (i * 1000),
                heading=None,
                speed=250,
            )
        env._initial_aircraft_count = len(env.engine.aircrafts)
        env._previous_observation = env._build_observation()

    def grade(self, env: "ATCEnv") -> float:
        """
        Calculate score for traffic pattern task.

        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0

        all_landed = self._all_landed(env)
        collision = self._has_collision(env)
        runway_incursion = self._has_runway_incursion(env)
        sim_time = env.engine.simulation_time if env.engine else 0.0

        if all_landed:
            score += 0.4

        if not collision:
            score += 0.3

        if not runway_incursion:
            score += 0.2

        if all_landed and not collision and not runway_incursion:
            if sim_time <= self.AVG_TIME_THRESHOLD_SECONDS:
                score += 0.1
            else:
                time_ratio = max(
                    0.0,
                    1.0
                    - (sim_time - self.AVG_TIME_THRESHOLD_SECONDS)
                    / self.AVG_TIME_THRESHOLD_SECONDS,
                )
                score += 0.1 * time_ratio

        return max(0.0, min(1.0, score))

    def is_complete(self, env: "ATCEnv") -> bool:
        """Check if episode should end."""
        if env.engine is None:
            return False

        if env.engine.is_terminal:
            return True

        if self._all_landed(env):
            return True

        if self._has_collision(env):
            return True

        if self._has_exited_airspace(env):
            return True

        return False

    def _all_landed(self, env: "ATCEnv") -> bool:
        """Check if all aircraft have landed."""
        assert env.engine is not None
        if not env.engine.aircrafts:
            return False
        for ac in env.engine.aircrafts.values():
            if ac.state not in ("LANDING", "TAXIING"):
                return False
        return True

    def _has_collision(self, env: "ATCEnv") -> bool:
        """Check if collision occurred."""
        assert env.engine is not None
        for event in env.engine.event_buffer:
            if event.get("type") == "CRASH":
                return True
            if event.get("type") == "SEPARATION_VIOLATION":
                return True
        return False

    def _has_runway_incursion(self, env: "ATCEnv") -> bool:
        """Check if runway incursion occurred."""
        assert env.engine is not None
        for event in env.engine.event_buffer:
            if event.get("type") == "RUNWAY_INCURSION":
                return True
            if event.get("type") == "RUNWAY_CONFLICT":
                return True
        return False

    def _has_exited_airspace(self, env: "ATCEnv") -> bool:
        """Check if aircraft has exited airspace."""
        assert env.engine is not None
        for ac in env.engine.aircrafts.values():
            if ac.altitude < 0 or ac.altitude > 45000:
                return True
            dist = math.sqrt(ac.x**2 + ac.y**2)
            if dist > 100:
                return True
        return False

    @property
    def difficulty(self) -> str:
        """Return difficulty level."""
        return "medium"
