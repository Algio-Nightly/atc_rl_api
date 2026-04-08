"""SingleApproach task - Easy task with 1 aircraft simple approach."""

import math
from typing import TYPE_CHECKING

from .base import Task

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class SingleApproachTask(Task):
    """
    Easy task: 1 aircraft, simple approach.

    Scenario: A single aircraft approaches for landing. The agent must
    guide it to a safe landing while avoiding collision with terrain
    or other traffic (though there's no other traffic in this scenario).

    Scoring:
        - 0.5 for successful landing
        - 0.3 for no collision
        - 0.2 for time < 1.5x optimal (optimal ~200 seconds)
    """

    OPTIMAL_TIME_SECONDS = 200.0
    MAX_TIME_MULTIPLIER = 1.5
    SPAWN_DISTANCE_KM = 15.0

    def setup(self, env: "ATCEnv") -> None:
        """Configure environment for single approach task."""
        env.reset(task="single_approach", skip_spawn=True)
        upwind_gates = env._select_upwind_gates()
        gate = upwind_gates[0] if upwind_gates else "N"
        env.engine.add_aircraft(
            callsign="RL001",
            ac_type="B737",
            weight_class="Heavy",
            gate=gate,
            altitude=8000,
            heading=None,
            speed=250,
        )
        env._initial_aircraft_count = len(env.engine.aircrafts)
        env._previous_observation = env._build_observation()

    def grade(self, env: "ATCEnv") -> float:
        """
        Calculate score for single approach task.

        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0

        landed = self._has_landed(env)
        collision = self._has_collision(env)
        sim_time = env.engine.simulation_time if env.engine else 0.0

        if landed:
            score += 0.5

        if not collision:
            score += 0.3

        if landed and not collision:
            optimal_time = self.OPTIMAL_TIME_SECONDS
            max_time = optimal_time * self.MAX_TIME_MULTIPLIER
            if sim_time <= max_time:
                score += 0.2
            else:
                time_ratio = max(0.0, 1.0 - (sim_time - max_time) / max_time)
                score += 0.2 * time_ratio

        return max(0.0, min(1.0, score))

    def is_complete(self, env: "ATCEnv") -> bool:
        """Check if episode should end."""
        if env.engine is None:
            return False

        if env.engine.is_terminal:
            return True

        if self._has_landed(env):
            return True

        if self._has_collision(env):
            return True

        if self._has_exited_airspace(env):
            return True

        return False

    def _has_landed(self, env: "ATCEnv") -> bool:
        """Check if aircraft has landed."""
        assert env.engine is not None
        for ac in env.engine.aircrafts.values():
            if ac.state == "LANDING" or ac.state == "TAXIING":
                return True
            if ac.state == "ENROUTE" or ac.state == "APPROACH":
                pass
        return False

    def _has_collision(self, env: "ATCEnv") -> bool:
        """Check if collision occurred."""
        assert env.engine is not None
        for event in env.engine.event_buffer:
            if event.get("type") == "CRASH":
                return True
            if event.get("type") == "SEPARATION_VIOLATION":
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
        return "easy"
