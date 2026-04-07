"""Task base class and grading system for ATC RL environment."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rl_env.environment import ATCEnv


class Task(ABC):
    """
    Abstract base class for ATC RL tasks.

    Tasks define the setup, grading criteria, and completion conditions
    for different competition scenarios.
    """

    @abstractmethod
    def setup(self, env: "ATCEnv") -> None:
        """
        Configure environment for this task.

        Args:
            env: ATCEnv instance to configure
        """
        raise NotImplementedError("Subclasses must implement setup()")

    @abstractmethod
    def grade(self, env: "ATCEnv") -> float:
        """
        Return score 0.0-1.0 based on episode performance.

        Args:
            env: ATCEnv instance with completed episode

        Returns:
            Score between 0.0 and 1.0
        """
        raise NotImplementedError("Subclasses must implement grade()")

    @abstractmethod
    def is_complete(self, env: "ATCEnv") -> bool:
        """
        Return True if episode should end.

        Args:
            env: ATCEnv instance to check

        Returns:
            True if episode is complete, False otherwise
        """
        raise NotImplementedError("Subclasses must implement is_complete()")

    @property
    def name(self) -> str:
        """Return task name."""
        return self.__class__.__name__

    @property
    def difficulty(self) -> str:
        """Return difficulty level: easy, medium, or hard."""
        return "unknown"
