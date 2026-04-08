"""Base rubric abstract class for ATC RL environment rewards."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rl_env.models import ATCAction, ATCObservation


class BaseRubric(ABC):
    """
    Abstract base class for all rubric reward calculators.

    Rubrics compute scalar rewards based on actions and observations.
    They support composition via __add__ and __mul__ for combining
    multiple rubrics into weighted sums.
    """

    def __init__(self, weight: float = 1.0):
        """
        Initialize rubric with an optional weight.

        Args:
            weight: Weight for this rubric in a weighted sum (default: 1.0)
        """
        self._weight = weight

    @property
    def weight(self) -> float:
        """Get the rubric's weight for weighted sums."""
        return self._weight

    @weight.setter
    def weight(self, value: float) -> None:
        """Set the rubric's weight for weighted sums."""
        self._weight = value

    @abstractmethod
    def forward(
        self,
        action: "ATCAction",
        observation: "ATCObservation",
        events: list[dict] | None = None,
    ) -> float:
        """
        Compute the reward for this rubric.

        Args:
            action: The action taken by the agent
            observation: The current observation from the environment
            events: Optional list of engine events for authoritative signal detection

        Returns:
            Scalar reward value (should be bounded roughly [-10, +10] per step)
        """
        raise NotImplementedError("Subclasses must implement forward()")

    def __add__(self, other: "BaseRubric") -> "WeightedSum":
        """
        Combine two rubrics into a weighted sum.

        Args:
            other: Another rubric to combine

        Returns:
            WeightedSum rubric combining both
        """
        if not isinstance(other, BaseRubric):
            return NotImplemented
        return WeightedSum([self, other])

    def __mul__(self, scalar: float) -> "BaseRubric":
        """
        Scale this rubric by a scalar weight.

        Args:
            scalar: Weight multiplier

        Returns:
            New rubric with scaled weight
        """
        new_rubric = self.__class__.__new__(self.__class__)
        new_rubric.__init__(weight=self._weight * scalar)
        return new_rubric

    def __rmul__(self, scalar: float) -> "BaseRubric":
        """Support scalar * rubric syntax."""
        return self.__mul__(scalar)


class WeightedSum(BaseRubric):
    """
    Composite rubric that sums weighted contributions from multiple rubrics.
    """

    def __init__(self, rubrics: list[BaseRubric] | None = None):
        """
        Initialize weighted sum with optional list of rubrics.

        Args:
            rubrics: List of rubrics to combine
        """
        super().__init__(weight=1.0)
        self._rubrics: list[BaseRubric] = [] if rubrics is None else rubrics

    def add(self, rubric: BaseRubric) -> "WeightedSum":
        """
        Add a rubric to this weighted sum.

        Args:
            rubric: Rubric to add

        Returns:
            Self for chaining
        """
        self._rubrics.append(rubric)
        return self

    def forward(
        self,
        action: "ATCAction",
        observation: "ATCObservation",
        events: list[dict] | None = None,
    ) -> float:
        total = 0.0
        for rubric in self._rubrics:
            total += rubric.weight * rubric.forward(action, observation, events=events)
        return total

    def __mul__(self, scalar: float) -> "WeightedSum":
        """Scale all rubric weights by scalar."""
        new_sum = WeightedSum(self._rubrics.copy())
        for rubric in new_sum._rubrics:
            rubric.weight *= scalar
        return new_sum
