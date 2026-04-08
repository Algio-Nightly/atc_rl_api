"""MixedOperationsTask - Hard task with arrivals and departures."""

from .departure import DepartureTask
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class MixedOperationsTask(DepartureTask):
    """Hard task: 6 aircraft (3 arrivals + 3 departures)."""

    def setup(self, env: "ATCEnv") -> None:
        env.reset(task="mixed_operations")

    def grade(self, env: "ATCEnv") -> float:
        score = 0.0
        departures = self._count_departures(env)
        landings = self._count_landings(env)
        total = 6

        completion = (departures + landings) / total
        score += 0.4 * completion
        if not self._has_collision(env):
            score += 0.3
        if not self._has_separation_violation(env):
            score += 0.2
        sim_time = env.engine.simulation_time if env.engine else 0.0
        if sim_time <= 900.0:
            score += 0.1
        else:
            time_ratio = max(0.0, 1.0 - (sim_time - 900.0) / 900.0)
            score += 0.1 * time_ratio

        return max(0.0, min(1.0, score))

    def _count_landings(self, env: "ATCEnv") -> int:
        assert env.engine is not None
        count = 0
        for event in env.engine.event_buffer:
            if event.get("type") == "SUCCESSFUL_LANDING":
                count += 1
        return count

    def _has_separation_violation(self, env: "ATCEnv") -> bool:
        assert env.engine is not None
        for event in env.engine.event_buffer:
            if event.get("type") == "SEPARATION_VIOLATION":
                return True
        return False

    def is_complete(self, env: "ATCEnv") -> bool:
        if env.engine is None:
            return False
        if env.engine.is_terminal:
            return True
        if self._all_departed_or_exited(env) and self._all_landed_or_exited(env):
            return True
        if self._has_collision(env):
            return True
        return False

    def _all_landed_or_exited(self, env: "ATCEnv") -> bool:
        assert env.engine is not None
        for ac in env.engine.aircrafts.values():
            if ac.state in ("ENROUTE", "APPROACH", "HOLDING", "FINAL"):
                return False
        return True

    @property
    def difficulty(self) -> str:
        return "hard"
