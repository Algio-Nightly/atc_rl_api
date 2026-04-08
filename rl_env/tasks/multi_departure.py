"""MultiDepartureTask - Medium task with 3 departure aircraft."""

from .departure import DepartureTask
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class MultiDepartureTask(DepartureTask):
    """Medium task: 3 departure aircraft."""

    def setup(self, env: "ATCEnv") -> None:
        env.reset(task="multi_departure")

    def grade(self, env: "ATCEnv") -> float:
        score = 0.0
        departures = self._count_departures(env)
        total = 3

        score += 0.5 * (departures / total)
        if not self._has_collision(env):
            score += 0.3
        sim_time = env.engine.simulation_time if env.engine else 0.0
        if sim_time <= 600.0:
            score += 0.2
        else:
            time_ratio = max(0.0, 1.0 - (sim_time - 600.0) / 600.0)
            score += 0.2 * time_ratio

        return max(0.0, min(1.0, score))

    def is_complete(self, env: "ATCEnv") -> bool:
        if env.engine is None:
            return False
        if env.engine.is_terminal:
            return True
        if self._all_departed_or_exited(env):
            return True
        if self._has_collision(env):
            return True
        return False

    @property
    def difficulty(self) -> str:
        return "medium"
