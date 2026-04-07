"""Real LLM API tests for ATC command generation.

These tests make actual API calls to the LLM and validate responses.
Requires HF_TOKEN environment variable to be set.

Run with: pytest -m "llm and slow" rl_env/tests/test_llm_commands_real.py
"""

import os
import pytest

from rl_env.client import LLMClient
from rl_env.prompts.atc_prompt import generate_atc_prompt
from rl_env.parsers import parse, ParseError
from rl_env.models import (
    ATCObservation,
    AircraftObservation,
    Position,
    Motion,
    Intent,
    Separation,
    AirportStatus,
    Wind,
    Metrics,
)


# Skip entire module if HF_TOKEN not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("HF_TOKEN"),
    reason="HF_TOKEN not set - skipping LLM tests",
)


@pytest.fixture
def llm_client():
    """Create LLM client with HF_TOKEN from environment."""
    token = os.environ.get("HF_TOKEN")
    if not token:
        pytest.skip("HF_TOKEN not set")
    return LLMClient(hf_token=token)


def create_enroute_observation(callsign: str = "AAL123") -> ATCObservation:
    """Create a test observation with aircraft in ENROUTE state."""
    return ATCObservation(
        airport_status=AirportStatus(
            active_runways=["27L", "27R"],
            runway_occupancy={"27L": None, "27R": None},
            wind=Wind.example(),
        ),
        aircraft=[
            AircraftObservation(
                callsign=callsign,
                position=Position(
                    segment="North-East",
                    distance=12.5,
                    altitude=5000,
                    target_altitude=3000,
                ),
                motion=Motion(
                    heading=285.0,
                    target_heading=270.0,
                    speed=250,
                    target_speed=210,
                ),
                intent=Intent(
                    state="ENROUTE",
                    assigned_runway=None,
                    distance_to_threshold=None,
                    next_waypoint="JUTES",
                ),
                alerts=[],
                separation=Separation(
                    closest_traffic=None,
                    distance=None,
                    conflict_risk="none",
                ),
            )
        ],
        metrics=Metrics.example(),
    )


def create_holding_observation(callsign: str = "UAL456") -> ATCObservation:
    """Create a test observation with aircraft in HOLDING state."""
    return ATCObservation(
        airport_status=AirportStatus(
            active_runways=["27L"],
            runway_occupancy={"27L": None},
            wind=Wind.example(),
        ),
        aircraft=[
            AircraftObservation(
                callsign=callsign,
                position=Position(
                    segment="North",
                    distance=8.0,
                    altitude=4000,
                    target_altitude=3000,
                ),
                motion=Motion(
                    heading=180.0,
                    target_heading=180.0,
                    speed=200,
                    target_speed=180,
                ),
                intent=Intent(
                    state="HOLDING",
                    assigned_runway=None,
                    distance_to_threshold=None,
                    next_waypoint="HOLDPT",
                ),
                alerts=[],
                separation=Separation(
                    closest_traffic=None,
                    distance=None,
                    conflict_risk="none",
                ),
            )
        ],
        metrics=Metrics.example(),
    )


def create_approach_observation(callsign: str = "DAL789") -> ATCObservation:
    """Create a test observation with aircraft in APPROACH state."""
    return ATCObservation(
        airport_status=AirportStatus(
            active_runways=["27L"],
            runway_occupancy={"27L": None},
            wind=Wind.example(),
        ),
        aircraft=[
            AircraftObservation(
                callsign=callsign,
                position=Position(
                    segment="South-East",
                    distance=5.0,
                    altitude=2000,
                    target_altitude=1000,
                ),
                motion=Motion(
                    heading=90.0,
                    target_heading=270.0,
                    speed=180,
                    target_speed=160,
                ),
                intent=Intent(
                    state="APPROACH",
                    assigned_runway="27L",
                    distance_to_threshold=5.0,
                    next_waypoint="ILS27L",
                ),
                alerts=[],
                separation=Separation(
                    closest_traffic=None,
                    distance=None,
                    conflict_risk="none",
                ),
            )
        ],
        metrics=Metrics.example(),
    )


def create_emergency_observation(callsign: str = "EME001") -> ATCObservation:
    """Create a test observation with emergency aircraft."""
    return ATCObservation(
        airport_status=AirportStatus(
            active_runways=["27L", "27R"],
            runway_occupancy={"27L": None, "27R": None},
            wind=Wind.example(),
        ),
        aircraft=[
            AircraftObservation(
                callsign=callsign,
                position=Position(
                    segment="North-West",
                    distance=15.0,
                    altitude=8000,
                    target_altitude=3000,
                ),
                motion=Motion(
                    heading=315.0,
                    target_heading=270.0,
                    speed=280,
                    target_speed=220,
                ),
                intent=Intent(
                    state="ENROUTE",
                    assigned_runway=None,
                    distance_to_threshold=None,
                    next_waypoint="DIRECT",
                ),
                alerts=["critical_emergency"],
                separation=Separation(
                    closest_traffic=None,
                    distance=None,
                    conflict_risk="none",
                ),
            )
        ],
        metrics=Metrics.example(),
    )


def create_collision_situation_observation() -> ATCObservation:
    """Create a test observation with two aircraft at collision risk."""
    return ATCObservation(
        airport_status=AirportStatus(
            active_runways=["27L"],
            runway_occupancy={"27L": None},
            wind=Wind.example(),
        ),
        aircraft=[
            AircraftObservation(
                callsign="CFL001",
                position=Position(
                    segment="North",
                    distance=10.0,
                    altitude=5000,
                    target_altitude=3000,
                ),
                motion=Motion(
                    heading=180.0,
                    target_heading=180.0,
                    speed=250,
                    target_speed=220,
                ),
                intent=Intent(
                    state="ENROUTE",
                    assigned_runway=None,
                    distance_to_threshold=None,
                    next_waypoint="JUTES",
                ),
                alerts=[],
                separation=Separation(
                    closest_traffic="CFL002",
                    distance=2.5,
                    conflict_risk="high",
                ),
            ),
            AircraftObservation(
                callsign="CFL002",
                position=Position(
                    segment="North",
                    distance=8.0,
                    altitude=4800,
                    target_altitude=3000,
                ),
                motion=Motion(
                    heading=180.0,
                    target_heading=180.0,
                    speed=250,
                    target_speed=220,
                ),
                intent=Intent(
                    state="ENROUTE",
                    assigned_runway=None,
                    distance_to_threshold=None,
                    next_waypoint="JUTES",
                ),
                alerts=[],
                separation=Separation(
                    closest_traffic="CFL001",
                    distance=2.5,
                    conflict_risk="high",
                ),
            ),
        ],
        metrics=Metrics.example(),
    )


def create_multi_aircraft_observation() -> ATCObservation:
    """Create a test observation with multiple aircraft."""
    return ATCObservation(
        airport_status=AirportStatus(
            active_runways=["27L", "27R"],
            runway_occupancy={"27L": None, "27R": None},
            wind=Wind.example(),
        ),
        aircraft=[
            AircraftObservation(
                callsign="AAL123",
                position=Position(
                    segment="North-East",
                    distance=12.5,
                    altitude=5000,
                    target_altitude=3000,
                ),
                motion=Motion(
                    heading=285.0,
                    target_heading=270.0,
                    speed=250,
                    target_speed=210,
                ),
                intent=Intent(
                    state="ENROUTE",
                    assigned_runway=None,
                    distance_to_threshold=None,
                    next_waypoint="JUTES",
                ),
                alerts=[],
                separation=Separation(
                    closest_traffic=None,
                    distance=None,
                    conflict_risk="none",
                ),
            ),
            AircraftObservation(
                callsign="UAL456",
                position=Position(
                    segment="South",
                    distance=15.0,
                    altitude=6000,
                    target_altitude=3000,
                ),
                motion=Motion(
                    heading=0.0,
                    target_heading=360.0,
                    speed=240,
                    target_speed=200,
                ),
                intent=Intent(
                    state="ENROUTE",
                    assigned_runway=None,
                    distance_to_threshold=None,
                    next_waypoint="HANKY",
                ),
                alerts=["low_fuel"],
                separation=Separation(
                    closest_traffic=None,
                    distance=None,
                    conflict_risk="none",
                ),
            ),
            AircraftObservation(
                callsign="DAL789",
                position=Position(
                    segment="West",
                    distance=8.0,
                    altitude=3000,
                    target_altitude=2000,
                ),
                motion=Motion(
                    heading=90.0,
                    target_heading=270.0,
                    speed=180,
                    target_speed=160,
                ),
                intent=Intent(
                    state="APPROACH",
                    assigned_runway="27L",
                    distance_to_threshold=6.0,
                    next_waypoint="ILS27L",
                ),
                alerts=[],
                separation=Separation(
                    closest_traffic=None,
                    distance=None,
                    conflict_risk="none",
                ),
            ),
        ],
        metrics=Metrics.example(),
    )


@pytest.mark.llm
@pytest.mark.slow
def test_llm_generates_vector_command(llm_client):
    """Test that LLM generates a valid VECTOR command."""
    obs = create_enroute_observation(callsign="AAL123")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)
    assert parsed["command"] == "VECTOR"
    assert parsed["callsign"] == "AAL123"
    assert "heading" in parsed
    assert isinstance(parsed["heading"], (int, float))
    assert 0 <= parsed["heading"] < 360


@pytest.mark.llm
@pytest.mark.slow
def test_llm_generates_altitude_command(llm_client):
    """Test that LLM generates a valid ALTITUDE command."""
    obs = create_enroute_observation(callsign="UAL456")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)
    assert parsed["command"] == "ALTITUDE"
    assert parsed["callsign"] == "UAL456"
    assert "altitude" in parsed
    assert isinstance(parsed["altitude"], (int, float))
    assert parsed["altitude"] > 0


@pytest.mark.llm
@pytest.mark.slow
def test_llm_generates_speed_command(llm_client):
    """Test that LLM generates a valid SPEED command."""
    obs = create_enroute_observation(callsign="DAL789")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)
    assert parsed["command"] == "SPEED"
    assert parsed["callsign"] == "DAL789"
    assert "speed" in parsed
    assert isinstance(parsed["speed"], (int, float))
    assert parsed["speed"] > 0


@pytest.mark.llm
@pytest.mark.slow
def test_llm_generates_hold_command(llm_client):
    """Test that LLM generates a valid HOLD command."""
    obs = create_enroute_observation(callsign="NWA321")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)
    assert parsed["command"] == "HOLD"
    assert parsed["callsign"] == "NWA321"


@pytest.mark.llm
@pytest.mark.slow
def test_llm_generates_direct_command(llm_client):
    """Test that LLM generates a valid DIRECT command."""
    obs = create_enroute_observation(callsign="AWE555")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)
    assert parsed["command"] == "DIRECT"
    assert parsed["callsign"] == "AWE555"
    assert "waypoint" in parsed


@pytest.mark.llm
@pytest.mark.slow
def test_llm_generates_approach_command(llm_client):
    """Test that LLM generates a valid APPROACH command."""
    obs = create_holding_observation(callsign="JBU123")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)
    assert parsed["command"] == "APPROACH"
    assert parsed["callsign"] == "JBU123"


@pytest.mark.llm
@pytest.mark.slow
def test_llm_generates_land_command(llm_client):
    """Test that LLM generates a valid LAND command."""
    obs = create_approach_observation(callsign="DAL789")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)
    assert parsed["command"] == "LAND"
    assert parsed["callsign"] == "DAL789"
    assert "runway" in parsed


@pytest.mark.llm
@pytest.mark.slow
def test_llm_generates_resume_command(llm_client):
    """Test that LLM generates a valid RESUME command."""
    obs = create_holding_observation(callsign="UAL456")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)
    assert parsed["command"] == "RESUME"
    assert parsed["callsign"] == "UAL456"


@pytest.mark.llm
@pytest.mark.slow
def test_llm_batch_commands(llm_client):
    """Test that LLM generates multiple commands for multi-aircraft scenario."""
    obs = create_multi_aircraft_observation()
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)

    # Handle single or batch response
    commands = parsed if isinstance(parsed, list) else [parsed]
    assert len(commands) >= 2, "Expected multiple commands for multi-aircraft scenario"

    # Verify all commands are valid
    for cmd in commands:
        assert "command" in cmd
        assert "callsign" in cmd
        # Verify callsigns match available aircraft
        valid_callsigns = ["AAL123", "UAL456", "DAL789"]
        assert cmd["callsign"] in valid_callsigns


@pytest.mark.llm
@pytest.mark.slow
def test_llm_emergency_priority(llm_client):
    """Test that LLM prioritizes emergency aircraft appropriately."""
    obs = create_emergency_observation(callsign="EME001")
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)

    # Emergency aircraft should be addressed
    commands = parsed if isinstance(parsed, list) else [parsed]
    emergency_commands = [cmd for cmd in commands if cmd.get("callsign") == "EME001"]
    assert len(emergency_commands) >= 1, (
        "LLM should issue command for emergency aircraft"
    )

    # Command should likely be VECTOR to direct to runway
    emergency_cmd = emergency_commands[0]
    assert emergency_cmd["command"] == "VECTOR", (
        "Emergency should get VECTOR command to nearest runway"
    )


@pytest.mark.llm
@pytest.mark.slow
def test_llm_collision_avoidance(llm_client):
    """Test that LLM generates collision avoidance commands."""
    obs = create_collision_situation_observation()
    prompt = generate_atc_prompt(obs)

    response = llm_client.generate(prompt)
    assert response, "LLM returned empty response"

    parsed = parse(response)

    commands = parsed if isinstance(parsed, list) else [parsed]
    assert len(commands) >= 1, "Expected at least one command for collision situation"

    # At least one command should address the high-conflict aircraft
    callsigns_involved = {cmd.get("callsign") for cmd in commands}
    collision_callsigns = {"CFL001", "CFL002"}
    assert callsigns_involved & collision_callsigns, (
        "LLM should issue commands for aircraft in collision situation"
    )
