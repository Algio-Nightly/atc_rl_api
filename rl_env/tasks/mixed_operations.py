"""MixedOperationsTask - Hard task with arrivals and departures."""

from .departure import DepartureTask
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class MixedOperationsTask(DepartureTask):
    """Hard task: 6 aircraft (3 arrivals + 3 departures)."""

    def setup(self, env: "ATCEnv") -> None:
        env.reset(task="mixed_operations", skip_spawn=True)
        upwind_gates = env._select_upwind_gates()
        arrival_gates = (
            [g for g in ["N", "S", "E"] if g in upwind_gates]
            if upwind_gates
            else ["N", "S", "E"]
        )
        while len(arrival_gates) < 3:
            arrival_gates.append(arrival_gates[0])
        arrival_gates = arrival_gates[:3]
        arrival_ac_types = ["B737", "A320", "B777"]
        arrival_weight_classes = ["Heavy", "Medium", "Heavy"]
        for i, gate in enumerate(arrival_gates):
            env.engine.add_aircraft(
                callsign=f"RL{i + 1:03d}",
                ac_type=arrival_ac_types[i],
                weight_class=arrival_weight_classes[i],
                gate=gate,
                altitude=8000 + i * 1000,
                heading=None,
                speed=250,
            )
        runway_id = (
            env.engine.active_runways[0] if env.engine.active_runways else "RWY_1"
        )
        departure_gates = ["G1", "G2", "G3"]
        departure_ac_types = ["E190", "A350", "B737"]
        for i in range(3):
            env.engine.spawn_departure(
                callsign=f"RL{3 + i + 1:03d}",
                ac_type=departure_ac_types[i],
                runway_id=runway_id,
                gate_id="N",
                terminal_gate_id=departure_gates[i],
            )
        env._initial_aircraft_count = len(env.engine.aircrafts)
        env._previous_observation = env._build_observation()

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
