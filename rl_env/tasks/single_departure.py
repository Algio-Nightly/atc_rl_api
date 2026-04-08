"""SingleDepartureTask - Easy task with 1 departure aircraft."""

from .departure import DepartureTask
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class SingleDepartureTask(DepartureTask):
    """Easy task: 1 departure aircraft."""

    def setup(self, env: "ATCEnv") -> None:
        env.reset(task="single_departure", skip_spawn=True)
        runway_id = (
            env.engine.active_runways[0] if env.engine.active_runways else "RWY_1"
        )
        env.engine.spawn_departure(
            callsign="RL001",
            ac_type="B737",
            runway_id=runway_id,
            gate_id="N",
            terminal_gate_id="G1",
        )
        env._initial_aircraft_count = len(env.engine.aircrafts)
        env._previous_observation = env._build_observation()

    def grade(self, env: "ATCEnv") -> float:
        score = 0.0
        if self._has_departed(env):
            score += 0.7
        if not self._has_collision(env):
            score += 0.3
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
        return "easy"
