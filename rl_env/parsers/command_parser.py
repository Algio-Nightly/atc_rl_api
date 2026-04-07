"""ATC Command Parser - Converts LLM text output into structured command dictionaries."""

from typing import Any, List, Union


class ParseError(Exception):
    """Custom exception raised when command parsing fails."""

    def __init__(self, message: str, raw_input: str = ""):
        self.raw_input = raw_input
        super().__init__(message)


# Supported ATC commands
SUPPORTED_COMMANDS = {
    "VECTOR",
    "ALTITUDE",
    "SPEED",
    "HOLD",
    "DIRECT",
    "APPROACH",
    "LAND",
    "RESUME",
    "TAXI",
    "LINE_UP",
    "TAKEOFF",
}


def parse(command_string: str) -> Union[dict, List[dict]]:
    """
    Parse an ATC command string into a structured dictionary.

    Supports:
    - Single commands: "ATC VECTOR AAL123 270"
    - Batch commands (newline separated): "ATC VECTOR AAL123 270\\nATC ALTITUDE BBB456 3000"
    - Both uppercase and lowercase input
    - Extra whitespace

    Args:
        command_string: Raw command string from LLM

    Returns:
        Single dict for single command, List[dict] for batch commands

    Raises:
        ParseError: If command format is invalid

    Examples:
        >>> parse("ATC VECTOR AAL123 270")
        {'command': 'VECTOR', 'callsign': 'AAL123', 'heading': 270}

        >>> parse("ATC VECTOR AAL123 270\\nATC ALTITUDE BBB456 3000")
        [{'command': 'VECTOR', 'callsign': 'AAL123', 'heading': 270},
         {'command': 'ALTITUDE', 'callsign': 'BBB456', 'altitude': 3000}]
    """
    if not command_string or not isinstance(command_string, str):
        raise ParseError("Command string is empty or invalid", raw_input=command_string)

    # Normalize: strip and convert to uppercase
    normalized = command_string.strip().upper()

    # Check for ATC prefix
    if not normalized.startswith("ATC"):
        raise ParseError(
            f"Command must start with 'ATC' prefix, got: {command_string[:50]}",
            raw_input=command_string,
        )

    # Split by newlines for batch processing
    lines = normalized.split("\n")
    lines = [line.strip() for line in lines if line.strip()]

    if not lines:
        raise ParseError(
            "No commands found after stripping whitespace", raw_input=command_string
        )

    # Parse each line
    results = [_parse_single_line(line, command_string) for line in lines]

    # Return single dict if only one command, otherwise list
    if len(results) == 1:
        return results[0]
    return results


def _parse_single_line(line: str, original_input: str) -> dict:
    """
    Parse a single ATC command line into a dictionary.

    Args:
        line: A single normalized command line
        original_input: The original unparsed input for error reporting

    Returns:
        Parsed command dictionary

    Raises:
        ParseError: If command format is invalid
    """
    # Split by whitespace
    parts = line.split()

    if len(parts) < 2:
        raise ParseError(
            f"Invalid command format: '{line}'. Expected 'ATC <COMMAND> <CALLSIGN> [PARAMETERS]'",
            raw_input=original_input,
        )

    # Validate ATC prefix
    if parts[0] != "ATC":
        raise ParseError(
            f"Command must start with 'ATC', got: {parts[0]}", raw_input=original_input
        )

    # Extract command and validate
    command = parts[1]
    if command not in SUPPORTED_COMMANDS:
        raise ParseError(
            f"Unknown ATC command: '{command}'. Supported: {sorted(SUPPORTED_COMMANDS)}",
            raw_input=original_input,
        )

    # VECTOR, ALTITUDE, SPEED, DIRECT, LAND, TAXI require callsign + parameter
    if command in ("VECTOR", "ALTITUDE", "SPEED", "DIRECT", "LAND", "TAXI"):
        if len(parts) < 3:
            raise ParseError(
                f"'{command}' command requires callsign and value. Format: ATC {command} <CALLSIGN> <VALUE>",
                raw_input=original_input,
            )
        callsign = parts[2]
        value = parts[3] if len(parts) > 3 else None

        if value is None:
            raise ParseError(
                f"'{command}' command requires a value parameter. Format: ATC {command} <CALLSIGN> <VALUE>",
                raw_input=original_input,
            )

        result: dict[str, Any] = {
            "command": command,
            "callsign": callsign,
        }

        if command == "VECTOR":
            result["heading"] = _parse_number(value, "heading", original_input)
        elif command == "ALTITUDE":
            result["altitude"] = _parse_number(value, "altitude", original_input)
        elif command == "SPEED":
            result["speed"] = _parse_number(value, "speed", original_input)
        elif command == "DIRECT":
            result["waypoint"] = value
        elif command == "LAND":
            result["runway"] = value
        elif command == "TAXI":
            result["runway"] = value

        return result

    # HOLD command: ATC HOLD <CALLSIGN> [WAYPOINT] [ALTITUDE]
    elif command == "HOLD":
        if len(parts) < 3:
            raise ParseError(
                f"'HOLD' command requires callsign. Format: ATC HOLD <CALLSIGN> [WAYPOINT] [ALTITUDE]",
                raw_input=original_input,
            )
        callsign = parts[2]
        waypoint = parts[3] if len(parts) > 3 else None
        altitude = parts[4] if len(parts) > 4 else None

        result: dict[str, Any] = {
            "command": command,
            "callsign": callsign,
        }

        if waypoint is not None:
            result["waypoint"] = waypoint
        if altitude is not None:
            result["altitude"] = _parse_number(altitude, "altitude", original_input)

        return result

    # APPROACH, RESUME, LINE_UP, and TAKEOFF commands: only require callsign
    elif command in ("APPROACH", "RESUME", "LINE_UP", "TAKEOFF"):
        if len(parts) < 3:
            raise ParseError(
                f"'{command}' command requires callsign. Format: ATC {command} <CALLSIGN>",
                raw_input=original_input,
            )
        return {
            "command": command,
            "callsign": parts[2],
        }

    # Should not reach here since we validate command earlier
    raise ParseError(f"Unhandled command: '{command}'", raw_input=original_input)


def _parse_number(
    value: str, param_name: str, original_input: str
) -> Union[int, float]:
    """
    Parse a string value into a number (int or float).

    Args:
        value: String value to parse
        param_name: Name of parameter for error messages
        original_input: Original input for error reporting

    Returns:
        Parsed number (int if whole number, float otherwise)

    Raises:
        ParseError: If value cannot be parsed as a number
    """
    try:
        # Try int first
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        raise ParseError(
            f"Invalid {param_name} value: '{value}'. Must be a number.",
            raw_input=original_input,
        )
