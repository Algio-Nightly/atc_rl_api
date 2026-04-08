"""DepartureTask - Base class for departure tasks."""

import math
from typing import TYPE_CHECKING
from .base import Task

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class DepartureTask(Task):
    """Base class for departure tasks with shared grading logic."""

    def _has_departed(self, env: "ATCEnv") -> bool:
        assert env.engine is not None
        for event in env.engine.event_buffer:
            if event.get("type") == "SUCCESSFUL_DEPARTURE":
                return True
        return False

    def _all_departed_or_exited(self, env: "ATCEnv") -> bool:
        assert env.engine is not None
        if not env.engine.aircrafts:
            return True
        for ac in env.engine.aircrafts.values():
            if ac.state in (
                "ON_GATE",
                "TAXIING",
                "HOLDING_SHORT",
                "LINE_UP",
                "TAKEOFF_ROLL",
            ):
                return False
        return True

    def _has_collision(self, env: "ATCEnv") -> bool:
        assert env.engine is not None
        for event in env.engine.event_buffer:
            if event.get("type") == "CRASH":
                return True
        return False

    def _count_departures(self, env: "ATCEnv") -> int:
        assert env.engine is not None
        count = 0
        for event in env.engine.event_buffer:
            if event.get("type") == "SUCCESSFUL_DEPARTURE":
                count += 1
        return count
