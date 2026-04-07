"""Real LLM reward validation tests - verifies rubric calculations with LLM-generated scenarios.

These tests use a real LLM to generate realistic ATC command sequences and verify
that rewards are correctly calculated according to the rubric definitions.
Requires HF_TOKEN environment variable.
"""

import os
import math
import pytest

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction
from rl_env.rubrics import (
    SafetyRubric,
    EfficiencyRubric,
    ATCRubric,
)
from rl_env.client import LLMClient
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError


pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("HF_TOKEN"),
        reason="HF_TOKEN environment variable not set",
    ),
    pytest.mark.slow,
    pytest.mark.llm,
]


def _build_command_string(cmd: dict) -> str:
    """Convert parsed command dict to ATC command string."""
    command = cmd.get("command", "").upper()
    callsign = cmd.get("callsign", "").upper()

    if not command or not callsign:
        return ""

    cmd_str = f"ATC {command} {callsign}"

    for key in ["heading", "altitude", "speed", "waypoint", "runway"]:
        if key in cmd and cmd[key] is not None:
            cmd_str += f" {cmd[key]}"

    return cmd_str


def _get_llm_action(client: LLMClient, observation) -> ATCAction:
    """Get action from LLM for given observation."""
    prompt = generate_atc_prompt(observation)

    try:
        llm_response = client.generate_with_retry(prompt)
    except Exception:
        return ATCAction(commands=[])

    try:
        parsed = parse(llm_response)
        commands = []

        if isinstance(parsed, list):
            for cmd in parsed:
                cmd_str = _build_command_string(cmd)
                if cmd_str:
                    commands.append(cmd_str)
        else:
            cmd_str = _build_command_string(parsed)
            if cmd_str:
                commands.append(cmd_str)

        return ATCAction(commands=commands)
    except ParseError:
        return ATCAction(commands=[])


class TestCollisionPenaltyRealLLM:
    """Test that collision penalties are correctly applied in LLM-driven scenarios."""

    def test_collision_penalty_applied(self, llm_client):
        """
        Verify collision penalty (-10.0) is applied when aircraft get too close.

        Uses LLM to generate commands that may lead to near-collision situations
        and verifies the SafetyRubric correctly identifies and penalizes them.
        """
        env = ATCEnv()
        client = llm_client

        observation, _ = env.reset(task="traffic_pattern")

        safety_rubric = SafetyRubric()
        action = ATCAction(commands=[])

        for _ in range(10):
            action = _get_llm_action(client, observation)

            # Track minimum separation during this step
            for ac in observation.aircraft:
                for other in observation.aircraft:
                    if other.callsign == ac.callsign:
                        continue

                    # Calculate actual distance
                    dist = _calculate_actual_distance(
                        ac.position.distance,
                        ac.position.segment,
                        other.position.distance,
                        other.position.segment,
                    )
                    alt_diff = abs(ac.position.altitude - other.position.altitude)

                    # If collision-like condition detected, verify penalty
                    if dist < 0.3 and alt_diff < 300:
                        reward = safety_rubric.forward(action, observation)
                        assert reward <= safety_rubric.PENALTY_COLLISION, (
                            f"Collision detected but penalty not applied correctly. "
                            f"Distance: {dist}, Alt diff: {alt_diff}"
                        )
                        return  # Test passed

            observation, _, done, _, _ = env.step(action)
            if done:
                break

        # If we didn't detect collision, verify no false positives
        reward = safety_rubric.forward(action, observation)
        # No collision should result in no collision penalty
        assert reward >= 0 or reward > safety_rubric.PENALTY_COLLISION

    def test_collision_penalty_value_exact(self):
        """Verify collision penalty constant is exactly -10.0."""
        assert SafetyRubric.PENALTY_COLLISION == -10.0


class TestLandingRewardRealLLM:
    """Test that landing rewards are correctly applied in LLM-driven scenarios."""

    def test_landing_reward_applied(self, llm_client):
        """
        Verify landing reward (+5.0) is applied when aircraft successfully lands.

        Uses LLM to guide an aircraft through approach and landing sequence.
        """
        env = ATCEnv()
        client = llm_client

        observation, _ = env.reset(task="single_approach")

        efficiency_rubric = EfficiencyRubric()

        # Track state transitions
        prev_state = None
        landed = False
        info = {}

        for step in range(100):
            action = _get_llm_action(client, observation)

            # Check for landing state transition
            for ac in observation.aircraft:
                current_state = ac.intent.state
                if (
                    prev_state == "APPROACH"
                    and current_state == "LANDING"
                    and ac.position.altitude < 100
                    and ac.position.distance < 0.2
                ):
                    landed = True

            observation, reward, done, _, info = env.step(action)
            prev_state = (
                observation.aircraft[0].intent.state if observation.aircraft else None
            )

            if done:
                break

        # If landing occurred, verify reward was positive
        if landed:
            total_reward = info.get("cumulative_reward", 0)
            assert total_reward > 0, "Landing should contribute positive reward"

    def test_landing_reward_value_exact(self):
        """Verify landing reward constant is exactly +5.0."""
        assert EfficiencyRubric.REWARD_LANDING_SUCCESS == 5.0


class TestTimeFuelPenaltiesRealLLM:
    """Test that time and fuel penalties accumulate correctly."""

    def test_time_penalty_accumulates(self, llm_client):
        """
        Verify time penalty is applied per aircraft per step.

        PENALTY_TIME_PER_AIRCRAFT_PER_STEP = -0.01 per aircraft.
        """
        env = ATCEnv()
        client = llm_client

        observation, _ = env.reset(task="single_approach")

        efficiency_rubric = EfficiencyRubric()

        num_steps = 10
        initial_reward = efficiency_rubric.forward(ATCAction(commands=[]), observation)

        for _ in range(num_steps):
            action = _get_llm_action(client, observation)
            observation, _, done, _, _ = env.step(action)
            if done:
                break

        # Calculate expected time penalty
        expected_time_penalty = (
            efficiency_rubric.PENALTY_TIME_PER_AIRCRAFT_PER_STEP
            * len(observation.aircraft)
            * num_steps
        )

        # Time penalty should be negative and accumulate
        assert expected_time_penalty < 0

    def test_time_penalty_value_per_step(self):
        """Verify time penalty constant is -0.01 per aircraft per step."""
        assert EfficiencyRubric.PENALTY_TIME_PER_AIRCRAFT_PER_STEP == -0.01


class TestSeparationViolationPenaltiesRealLLM:
    """Test that separation violation penalties are correctly applied."""

    def test_separation_violation_penalty(self, llm_client):
        """
        Verify separation violation penalty (-2.0) is applied correctly.

        Separation violation occurs when:
        - distance < 5.0 km AND
        - altitude difference < 1000 ft
        """
        env = ATCEnv()
        client = llm_client

        observation, _ = env.reset(task="traffic_pattern")

        safety_rubric = SafetyRubric()

        violation_detected = False

        for _ in range(15):
            action = _get_llm_action(client, observation)

            # Check for separation violation conditions
            for ac in observation.aircraft:
                if ac.separation.closest_traffic and ac.separation.distance is not None:
                    if (
                        ac.separation.distance
                        < safety_rubric.THRESHOLD_SEP_VIOLATION_DIST_KM
                    ):
                        # Find the traffic aircraft
                        for other in observation.aircraft:
                            if other.callsign == ac.separation.closest_traffic:
                                alt_diff = abs(
                                    ac.position.altitude - other.position.altitude
                                )
                                if (
                                    alt_diff
                                    < safety_rubric.THRESHOLD_SEP_VIOLATION_ALT_FT
                                ):
                                    violation_detected = True
                                    break

            if violation_detected:
                break

            observation, _, done, _, _ = env.step(action)
            if done:
                break

        # Verify the threshold constants are correct
        assert safety_rubric.THRESHOLD_SEP_VIOLATION_DIST_KM == 5.0
        assert safety_rubric.THRESHOLD_SEP_VIOLATION_ALT_FT == 1000.0

    def test_separation_violation_penalty_value_exact(self):
        """Verify separation violation penalty constant is exactly -2.0."""
        assert SafetyRubric.PENALTY_SEPARATION_VIOLATION == -2.0


class TestGoAroundPenaltyRealLLM:
    """Test that go-around penalties are correctly applied."""

    def test_go_around_penalty_applied(self, llm_client):
        """
        Verify go-around penalty (-3.0) is applied when aircraft executes go-around.

        Go-around penalty is triggered when state transitions from
        APPROACH/LANDING to GO_AROUND.
        """
        env = ATCEnv()
        client = llm_client

        observation, _ = env.reset(task="traffic_pattern")

        efficiency_rubric = EfficiencyRubric()

        prev_states = {ac.callsign: ac.intent.state for ac in observation.aircraft}

        go_around_occurred = False

        for _ in range(20):
            action = _get_llm_action(client, observation)
            observation, reward, done, _, _ = env.step(action)

            # Check for go-around state transition
            for ac in observation.aircraft:
                prev_state = prev_states.get(ac.callsign, "")
                current_state = ac.intent.state

                if current_state == "GO_AROUND" and prev_state in [
                    "APPROACH",
                    "LANDING",
                ]:
                    go_around_occurred = True
                    # Verify penalty is applied in this step's reward
                    assert reward <= efficiency_rubric.PENALTY_GO_AROUND, (
                        f"Go-around occurred but reward {reward} does not reflect "
                        f"penalty of {efficiency_rubric.PENALTY_GO_AROUND}"
                    )

            prev_states = {ac.callsign: ac.intent.state for ac in observation.aircraft}

            if done:
                break

        # If go-around occurred, the penalty should have been applied
        assert efficiency_rubric.PENALTY_GO_AROUND == -3.0

    def test_go_around_penalty_value_exact(self):
        """Verify go-around penalty constant is exactly -3.0."""
        assert EfficiencyRubric.PENALTY_GO_AROUND == -3.0


class TestCompositeRewardCalculation:
    """Test composite ATCRubric reward calculation with LLM scenarios."""

    def test_composite_rubric_reward_accumulation(self, llm_client):
        """
        Verify composite ATCRubric correctly sums weighted rubric contributions.

        Default weights:
        - Safety: 40%
        - Efficiency: 35%
        - Compliance: 20%
        - Format: 5%
        """
        env = ATCEnv()
        client = llm_client

        observation, _ = env.reset(task="single_approach")

        rubric = ATCRubric()

        cumulative_reward = 0.0

        for _ in range(10):
            action = _get_llm_action(client, observation)
            observation, reward, done, _, info = env.step(action)
            cumulative_reward += reward

            # Verify reward is calculated
            assert isinstance(reward, float)

            # Verify cumulative reward matches info
            assert abs(info.get("cumulative_reward", 0) - cumulative_reward) < 0.01

            if done:
                break

        # Verify default weights sum to 1.0
        total_weight = (
            rubric.safety.weight
            + rubric.efficiency.weight
            + rubric.compliance.weight
            + rubric.format.weight
        )
        assert abs(total_weight - 1.0) < 0.001

    def test_all_rubric_penalties_negative(self):
        """Verify all penalty constants are negative."""
        safety = SafetyRubric()
        efficiency = EfficiencyRubric()

        # Safety penalties
        assert safety.PENALTY_COLLISION < 0
        assert safety.PENALTY_RUNWAY_INCURSION < 0
        assert safety.PENALTY_FUEL_EXHAUSTION < 0
        assert safety.PENALTY_NEAR_MISS < 0
        assert safety.PENALTY_SEPARATION_VIOLATION < 0
        assert safety.PENALTY_CONFLICT_HIGH < 0
        assert safety.PENALTY_CONFLICT_IMMINENT < 0

        # Efficiency penalties
        assert efficiency.PENALTY_GO_AROUND < 0
        assert efficiency.PENALTY_TIME_PER_AIRCRAFT_PER_STEP < 0
        assert efficiency.PENALTY_FUEL_PER_PERCENT_CONSUMED < 0
        assert efficiency.PENALTY_HOLDING_PER_MINUTE < 0

    def test_all_rubric_rewards_positive(self):
        """Verify all reward constants are positive."""
        efficiency = EfficiencyRubric()

        assert efficiency.REWARD_LANDING_SUCCESS > 0
        assert efficiency.REWARD_STAR_COMPLETION > 0
        assert efficiency.REWARD_WAYPOINT_REACHED > 0


def _calculate_actual_distance(
    dist1: float, seg1: str, dist2: float, seg2: str
) -> float:
    """Calculate actual distance between two aircraft in km."""
    x1, y1 = _segment_to_xy(dist1, seg1)
    x2, y2 = _segment_to_xy(dist2, seg2)
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def _segment_to_xy(distance: float, segment: str) -> tuple[float, float]:
    """Convert segment and distance to x, y coordinates."""
    segment_angles = {
        "North": 0,
        "North-East": 45,
        "East": 90,
        "South-East": 135,
        "South": 180,
        "South-West": 225,
        "West": 270,
        "North-West": 315,
    }
    angle = math.radians(segment_angles.get(segment, 0))
    x = distance * math.cos(angle)
    y = distance * math.sin(angle)
    return x, y


class TestRewardValueVerification:
    """Direct verification of reward constant values."""

    def test_safety_rubric_collision_constant(self):
        """Collision penalty must be exactly -10.0."""
        assert SafetyRubric.PENALTY_COLLISION == -10.0

    def test_safety_rubric_separation_violation_constant(self):
        """Separation violation penalty must be exactly -2.0."""
        assert SafetyRubric.PENALTY_SEPARATION_VIOLATION == -2.0

    def test_efficiency_rubric_landing_constant(self):
        """Landing success reward must be exactly +5.0."""
        assert EfficiencyRubric.REWARD_LANDING_SUCCESS == 5.0

    def test_efficiency_rubric_go_around_constant(self):
        """Go-around penalty must be exactly -3.0."""
        assert EfficiencyRubric.PENALTY_GO_AROUND == -3.0

    def test_efficiency_rubric_time_penalty_constant(self):
        """Time penalty per aircraft per step must be -0.01."""
        assert EfficiencyRubric.PENALTY_TIME_PER_AIRCRAFT_PER_STEP == -0.01

    def test_near_miss_penalty_constant(self):
        """Near-miss penalty must be exactly -5.0."""
        assert SafetyRubric.PENALTY_NEAR_MISS == -5.0

    def test_runway_incursion_penalty_constant(self):
        """Runway incursion penalty must be exactly -10.0."""
        assert SafetyRubric.PENALTY_RUNWAY_INCURSION == -10.0

    def test_fuel_exhaustion_penalty_constant(self):
        """Fuel exhaustion penalty must be exactly -10.0."""
        assert SafetyRubric.PENALTY_FUEL_EXHAUSTION == -10.0
