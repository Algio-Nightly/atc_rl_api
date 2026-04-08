"""Unit tests for redundant command penalties in ComplianceRubric."""

import pytest
from rl_env.rubrics.compliance import ComplianceRubric
from rl_env.models import ATCAction, ATCObservation, AircraftObservation, Position, Motion, Intent, AirportStatus, Metrics, Wind

def create_mock_obs(callsign="RL001", target_alt=8000, target_speed=250):
    return ATCObservation(
        airport_status=AirportStatus(active_runways=["RWY_1"], runway_occupancy={}, wind=Wind(heading=0, speed=0)),
        aircraft=[
            AircraftObservation(
                callsign=callsign,
                position=Position(segment="North", distance=40, altitude=8000, target_altitude=target_alt),
                motion=Motion(heading=180, target_heading=180, speed=250, target_speed=target_speed),
                intent=Intent(state="ENROUTE", assigned_runway=None, distance_to_threshold=None, next_waypoint="N"),
                alerts=[],
                separation=None,
                timing_stats=None,
                safety_metrics=None,
                command_rejections=[]
            )
        ],
        metrics=Metrics(simulation_time=0, planes_landed=0, planes_active=1)
    )

def test_diminishing_validity_reward():
    rubric = ComplianceRubric()
    obs = create_mock_obs()
    
    # First time issuing command
    action1 = ATCAction(commands=["ATC ALTITUDE RL001 5000"])
    reward1 = rubric.forward(action1, obs)
    assert reward1 > 0.05
    
    # Second time issuing SAME command (redundant)
    action2 = ATCAction(commands=["ATC ALTITUDE RL001 5000"])
    reward2 = rubric.forward(action2, obs)
    assert reward2 < reward1 # Should be lower (redundancy penalty + diminished reward)

def test_exponential_redundancy_penalty():
    rubric = ComplianceRubric()
    obs = create_mock_obs()
    
    rewards = []
    for _ in range(5):
        action = ATCAction(commands=["ATC ALTITUDE RL001 5000"])
        rewards.append(rubric.forward(action, obs))
        
    # Each successive penalty should be deeper than the last
    for i in range(1, len(rewards)):
        assert rewards[i] < rewards[i-1]
    
    # Eventually it should be negative (punishment)
    assert rewards[-1] < 0

def test_no_op_penalty():
    rubric = ComplianceRubric()
    # Plane is already targeting 8000ft
    obs = create_mock_obs(target_alt=8000)
    
    # Command it to 8000ft (no-op)
    action = ATCAction(commands=["ATC ALTITUDE RL001 8000"])
    reward = rubric.forward(action, obs)
    
    # Should be negative because it was a no-op
    assert reward < 0

def test_loop_detection():
    rubric = ComplianceRubric()
    obs = create_mock_obs()
    
    # Sequence: ALT 5000 -> ALT 6000 -> ALT 5000 (toggle)
    rubric.forward(ATCAction(commands=["ATC ALTITUDE RL001 5000"]), obs)
    rubric.forward(ATCAction(commands=["ATC ALTITUDE RL001 6000"]), obs)
    
    # The third command is a return to a very recent command (toggle)
    reward = rubric.forward(ATCAction(commands=["ATC ALTITUDE RL001 5000"]), obs)
    
    # Should be penalized as redundant in history
    assert reward < 0.05 
