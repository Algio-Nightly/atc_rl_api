"""Task classes for ATC RL environment competition scenarios."""

from .base import Task
from .single_approach import SingleApproachTask
from .traffic_pattern import TrafficPatternTask
from .storm_traffic import StormTrafficTask
from .departure import DepartureTask
from .single_departure import SingleDepartureTask
from .multi_departure import MultiDepartureTask
from .mixed_operations import MixedOperationsTask

__all__ = [
    "Task",
    "SingleApproachTask",
    "TrafficPatternTask",
    "StormTrafficTask",
    "DepartureTask",
    "SingleDepartureTask",
    "MultiDepartureTask",
    "MixedOperationsTask",
]
