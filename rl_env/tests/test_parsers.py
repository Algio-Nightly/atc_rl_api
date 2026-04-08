"""Unit tests for ATC command parser."""

import pytest
from rl_env.parsers import parse, ParseError


class TestAltitudeCommand:
    def test_altitude_basic(self):
        result = parse("ATC ALTITUDE AAL123 3000")
        assert result == {"command": "ALTITUDE", "callsign": "AAL123", "altitude": 3000}

    def test_altitude_lowercase(self):
        result = parse("atc altitude aal123 5000")
        assert result == {"command": "ALTITUDE", "callsign": "AAL123", "altitude": 5000}

    def test_altitude_float(self):
        result = parse("ATC ALTITUDE AAL123 3500.5")
        assert result == {
            "command": "ALTITUDE",
            "callsign": "AAL123",
            "altitude": 3500.5,
        }


class TestSpeedCommand:
    def test_speed_basic(self):
        result = parse("ATC SPEED AAL123 250")
        assert result == {"command": "SPEED", "callsign": "AAL123", "speed": 250}

    def test_speed_lowercase(self):
        result = parse("atc speed dal123 180")
        assert result == {"command": "SPEED", "callsign": "DAL123", "speed": 180}


class TestHoldCommand:
    def test_hold_callsign_only(self):
        result = parse("ATC HOLD AAL123")
        assert result == {"command": "HOLD", "callsign": "AAL123"}

    def test_hold_with_waypoint(self):
        result = parse("ATC HOLD AAL123 POM")
        assert result == {"command": "HOLD", "callsign": "AAL123", "waypoint": "POM"}

    def test_hold_with_waypoint_and_altitude(self):
        result = parse("ATC HOLD AAL123 POM 5000")
        assert result == {
            "command": "HOLD",
            "callsign": "AAL123",
            "waypoint": "POM",
            "altitude": 5000,
        }

    def test_hold_lowercase(self):
        result = parse("atc hold aal123 way 3000")
        assert result == {
            "command": "HOLD",
            "callsign": "AAL123",
            "waypoint": "WAY",
            "altitude": 3000,
        }


class TestDirectCommand:
    def test_direct_basic(self):
        result = parse("ATC DIRECT AAL123 POM")
        assert result == {"command": "DIRECT", "callsign": "AAL123", "waypoint": "POM"}

    def test_direct_lowercase(self):
        result = parse("atc direct aal123 jetix")
        assert result == {
            "command": "DIRECT",
            "callsign": "AAL123",
            "waypoint": "JETIX",
        }


class TestLandCommand:
    def test_land_basic(self):
        result = parse("ATC LAND AAL123 27L")
        assert result == {"command": "LAND", "callsign": "AAL123", "runway": "27L"}

    def test_land_lowercase(self):
        result = parse("atc land aal123 09r")
        assert result == {"command": "LAND", "callsign": "AAL123", "runway": "09R"}


class TestResumeCommand:
    def test_resume_basic(self):
        result = parse("ATC RESUME AAL123")
        assert result == {"command": "RESUME", "callsign": "AAL123"}

    def test_resume_lowercase(self):
        result = parse("atc resume dal123")
        assert result == {"command": "RESUME", "callsign": "DAL123"}


class TestBatchCommands:
    def test_batch_two_commands(self):
        result = parse("ATC ALTITUDE AAL123 5000\nATC ALTITUDE BBB456 3000")
        assert len(result) == 2
        assert result[0] == {"command": "ALTITUDE", "callsign": "AAL123", "altitude": 5000}
        assert result[1] == {
            "command": "ALTITUDE",
            "callsign": "BBB456",
            "altitude": 3000,
        }

    def test_batch_three_commands(self):
        result = parse(
            "ATC ALTITUDE AAL123 5000\nATC SPEED AAL123 250\nATC DIRECT AAL123 POM"
        )
        assert len(result) == 3
        assert result[0]["command"] == "ALTITUDE"
        assert result[1]["command"] == "SPEED"
        assert result[2]["command"] == "DIRECT"

    def test_batch_with_whitespace_lines(self):
        result = parse("ATC ALTITUDE AAL123 5000\n\nATC ALTITUDE BBB456 3000\n")
        assert len(result) == 2


class TestErrorHandling:
    def test_empty_string(self):
        with pytest.raises(ParseError) as exc_info:
            parse("")
        assert "empty" in str(exc_info.value).lower()

    def test_none_input(self):
        with pytest.raises(ParseError):
            parse(None)

    def test_invalid_prefix(self):
        with pytest.raises(ParseError) as exc_info:
            parse("INVALID COMMAND")
        assert "ATC" in str(exc_info.value)

    def test_unknown_command(self):
        with pytest.raises(ParseError) as exc_info:
            parse("ATC FOO AAL123")
        assert "FOO" in str(exc_info.value)
        assert "SUPPORTED" in str(exc_info.value).upper()

    def test_deprecated_commands_fail(self):
        for cmd in ["VECTOR", "APPROACH", "LINE_UP"]:
            with pytest.raises(ParseError) as exc_info:
                parse(f"ATC {cmd} AAL123")
            assert cmd in str(exc_info.value)
            assert "UNKNOWN" in str(exc_info.value).upper()

    def test_altitude_missing_value(self):
        with pytest.raises(ParseError) as exc_info:
            parse("ATC ALTITUDE AAL123")
        assert "ALTITUDE" in str(exc_info.value)

    def test_speed_missing_value(self):
        with pytest.raises(ParseError) as exc_info:
            parse("ATC SPEED AAL123")
        assert "SPEED" in str(exc_info.value)

    def test_direct_missing_waypoint(self):
        with pytest.raises(ParseError) as exc_info:
            parse("ATC DIRECT AAL123")
        assert "DIRECT" in str(exc_info.value)

    def test_land_missing_runway(self):
        with pytest.raises(ParseError) as exc_info:
            parse("ATC LAND AAL123")
        assert "LAND" in str(exc_info.value)

    def test_invalid_number(self):
        with pytest.raises(ParseError) as exc_info:
            parse("ATC ALTITUDE AAL123 ABC")
        assert "altitude" in str(exc_info.value).lower()

    def test_parse_error_contains_raw_input(self):
        try:
            parse("BAD INPUT")
        except ParseError as e:
            assert e.raw_input == "BAD INPUT"

    def test_resume_missing_callsign(self):
        with pytest.raises(ParseError) as exc_info:
            parse("ATC RESUME")
        assert "RESUME" in str(exc_info.value)


class TestEdgeCases:
    def test_extra_whitespace_between_parts(self):
        result = parse("ATC   ALTITUDE   AAL123   5000")
        assert result == {"command": "ALTITUDE", "callsign": "AAL123", "altitude": 5000}

    def test_newline_at_start(self):
        result = parse("\nATC ALTITUDE AAL123 5000")
        assert result == {"command": "ALTITUDE", "callsign": "AAL123", "altitude": 5000}

    def test_callsign_with_numbers(self):
        result = parse("ATC ALTITUDE UAL1234 5000")
        assert result == {"command": "ALTITUDE", "callsign": "UAL1234", "altitude": 5000}
