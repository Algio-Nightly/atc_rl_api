"""Tests for ATC RL environment rubrics."""

import pytest
from rl_env.models import (
    ATCAction,
    ATCObservation,
    AircraftObservation,
    Position,
    Motion,
    Intent,
    Separation,
    AirportStatus,
    Metrics,
    Wind,
)
from rl_env.rubrics import (
    BaseRubric,
    WeightedSum,
    SafetyRubric,
    EfficiencyRubric,
    ComplianceRubric,
    ATCRubric,
    FormatRubric,
)


def create_sample_observation(
    callsign="AAL123",
    state="ENROUTE",
    altitude=5000,
    target_altitude=3000,
    distance=12.5,
    segment="North-East",
    conflict_risk="none",
    closest_traffic=None,
    traffic_distance=None,
    alerts=None,
    runway_occupancy=None,
    next_waypoint="JUTES",
):
    if alerts is None:
        alerts = []
    if runway_occupancy is None:
        runway_occupancy = {}

    return ATCObservation(
        airport_status=AirportStatus(
            active_runways=["27L"],
            runway_occupancy=runway_occupancy,
            wind=Wind(heading=270, speed=15),
        ),
        aircraft=[
            AircraftObservation(
                callsign=callsign,
                position=Position(
                    segment=segment,
                    distance=distance,
                    altitude=altitude,
                    target_altitude=target_altitude,
                ),
                motion=Motion(
                    heading=285.0,
                    target_heading=270.0,
                    speed=250,
                    target_speed=210,
                ),
                intent=Intent(
                    state=state,
                    assigned_runway="27L" if state in ["APPROACH", "LANDING"] else None,
                    distance_to_threshold=8.5 if state == "APPROACH" else None,
                    next_waypoint=next_waypoint,
                ),
                alerts=alerts,
                separation=Separation(
                    closest_traffic=closest_traffic,
                    distance=traffic_distance,
                    conflict_risk=conflict_risk,
                ),
            )
        ],
        metrics=Metrics(
            simulation_time=100.0,
            planes_landed=0,
            planes_active=1,
        ),
    )


class TestBaseRubric:
    def test_abstract_class_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseRubric()

    def test_weight_property(self):
        rubric = SafetyRubric(weight=2.0)
        assert rubric.weight == 2.0

    def test_weight_setter(self):
        rubric = SafetyRubric()
        rubric.weight = 3.0
        assert rubric.weight == 3.0


class TestWeightedSum:
    def test_empty_weighted_sum(self):
        ws = WeightedSum()
        action = ATCAction(commands=[])
        obs = create_sample_observation()
        assert ws.forward(action, obs) == 0.0

    def test_single_rubric_weighted_sum(self):
        rubric = SafetyRubric(weight=0.5)
        ws = WeightedSum([rubric])
        action = ATCAction(commands=[])
        obs = create_sample_observation()
        result = ws.forward(action, obs)
        assert result == 0.5 * rubric.forward(action, obs)

    def test_multiple_rubrics_weighted_sum(self):
        safety = SafetyRubric(weight=0.4)
        efficiency = EfficiencyRubric(weight=0.6)
        ws = WeightedSum([safety, efficiency])
        action = ATCAction(commands=[])
        obs = create_sample_observation()

        expected = 0.4 * safety.forward(action, obs) + 0.6 * efficiency.forward(
            action, obs
        )
        assert ws.forward(action, obs) == expected


class TestSafetyRubric:
    def test_no_penalty_for_safe_aircraft(self):
        rubric = SafetyRubric()
        action = ATCAction(commands=[])
        obs = create_sample_observation(
            conflict_risk="none",
            altitude=5000,
        )
        reward = rubric.forward(action, obs)
        assert reward == 0.0

    def test_penalty_for_high_conflict_risk(self):
        rubric = SafetyRubric()
        action = ATCAction(commands=[])
        obs = create_sample_observation(
            conflict_risk="high",
            altitude=5000,
        )
        reward = rubric.forward(action, obs)
        assert reward == rubric.PENALTY_CONFLICT_HIGH

    def test_penalty_for_low_fuel_alert(self):
        rubric = SafetyRubric()
        action = ATCAction(commands=[])
        obs = create_sample_observation(alerts=["low_fuel"])
        reward = rubric.forward(action, obs)
        assert reward == rubric.PENALTY_FUEL_EXHAUSTION

    def test_penalty_for_separation_violation(self):
        rubric = SafetyRubric()
        action = ATCAction(commands=[])
        obs = create_sample_observation(
            conflict_risk="none",
            altitude=5000,
            closest_traffic="UAL456",
            traffic_distance=3.0,
        )
        reward = rubric.forward(action, obs)
        assert reward == rubric.PENALTY_SEPARATION_VIOLATION


class TestEfficiencyRubric:
    def test_time_penalty_per_aircraft(self):
        rubric = EfficiencyRubric()
        action = ATCAction(commands=[])
        obs = create_sample_observation()
        reward = rubric.forward(action, obs)
        expected_penalty = rubric.PENALTY_TIME_PER_AIRCRAFT_PER_STEP * 1
        assert reward == expected_penalty

    def test_waypoint_reached_reward(self):
        rubric = EfficiencyRubric()
        action = ATCAction(commands=[])

        obs1 = create_sample_observation()
        rubric.forward(action, obs1)

        obs2 = create_sample_observation(next_waypoint="CEDES")
        reward = rubric.forward(action, obs2)
        assert (
            reward
            >= rubric.REWARD_WAYPOINT_REACHED
            + rubric.PENALTY_TIME_PER_AIRCRAFT_PER_STEP
        )


class TestComplianceRubric:
    def test_valid_command_reward(self):
        rubric = ComplianceRubric()
        action = ATCAction(commands=["ATC VECTOR AAL123 270"])
        obs = create_sample_observation()
        reward = rubric.forward(action, obs)
        assert reward == rubric.REWARD_VALID_COMMAND

    def test_redundant_command_penalty(self):
        rubric = ComplianceRubric()

        action1 = ATCAction(commands=["ATC VECTOR AAL123 270"])
        obs = create_sample_observation()
        rubric.forward(action1, obs)

        action2 = ATCAction(commands=["ATC VECTOR AAL123 270"])
        reward = rubric.forward(action2, obs)
        assert reward == rubric.REWARD_VALID_COMMAND + rubric.PENALTY_REDUNDANT_COMMAND

    def test_glide_slope_compliance_reward(self):
        rubric = ComplianceRubric()
        action = ATCAction(commands=[])
        obs = create_sample_observation(
            state="APPROACH",
            altitude=2000,
            target_altitude=2000,
        )
        reward = rubric.forward(action, obs)
        assert reward == rubric.REWARD_GLIDE_SLOPE_COMPLIANCE


class TestFormatRubric:
    def test_well_formed_command(self):
        rubric = FormatRubric()
        action = ATCAction(commands=["ATC VECTOR AAL123 270"])
        obs = create_sample_observation()
        reward = rubric.forward(action, obs)
        assert reward == rubric.REWARD_WELL_FORMED

    def test_malformed_command(self):
        rubric = FormatRubric()
        action = ATCAction(commands=["INVALID"])
        obs = create_sample_observation()
        reward = rubric.forward(action, obs)
        assert reward == rubric.PENALTY_MALFORMED


class TestATCRubric:
    def test_default_weights_sum_to_one(self):
        assert ATCRubric.DEFAULT_WEIGHTS["safety"] == 0.35
        assert ATCRubric.DEFAULT_WEIGHTS["efficiency"] == 0.30
        assert ATCRubric.DEFAULT_WEIGHTS["compliance"] == 0.15
        assert ATCRubric.DEFAULT_WEIGHTS["format"] == 0.05
        assert ATCRubric.DEFAULT_WEIGHTS["departure"] == 0.15
        total = sum(ATCRubric.DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_composite_forward(self):
        rubric = ATCRubric()
        action = ATCAction(commands=["ATC VECTOR AAL123 270"])
        obs = create_sample_observation()
        reward = rubric.forward(action, obs)
        assert isinstance(reward, float)

    def test_custom_weights(self):
        rubric = ATCRubric(
            safety_weight=0.5,
            efficiency_weight=0.3,
            compliance_weight=0.15,
            format_weight=0.05,
        )
        assert rubric.safety.weight == 0.5
        assert rubric.efficiency.weight == 0.3
        assert rubric.compliance.weight == 0.15
        assert rubric.format.weight == 0.05


class TestRubricComposition:
    def test_rubric_addition(self):
        safety = SafetyRubric(weight=0.5)
        efficiency = EfficiencyRubric(weight=0.5)
        combined = safety + efficiency

        action = ATCAction(commands=[])
        obs = create_sample_observation()

        expected = 0.5 * safety.forward(action, obs) + 0.5 * efficiency.forward(
            action, obs
        )
        assert combined.forward(action, obs) == expected

    def test_rubric_multiplication(self):
        rubric = SafetyRubric(weight=1.0)
        scaled = rubric * 2.0

        action = ATCAction(commands=[])
        obs = create_sample_observation()

        assert scaled.weight == 2.0
        assert scaled.forward(action, obs) == 2.0 * rubric.forward(action, obs)
