"""ATC prompt generator for LLM-based control."""

from functools import lru_cache
from pathlib import Path

from rl_env.models import ATCObservation, AircraftObservation


# Full command set exposed to the model for each aircraft.
AVAILABLE_COMMANDS = [
    "ALTITUDE",
    "SPEED",
    "HOLD",
    "DIRECT",
    "APPROACH",
    "LAND",
    "GO_AROUND",
    "RESUME",
]


def _filter_disabled_commands_from_reference(reference_text: str) -> str:
    """Remove disabled command documentation from model-facing reference text."""
    filtered_lines: list[str] = []
    for line in reference_text.splitlines():
        upper_line = line.upper()
        if "ATC VECTOR" in upper_line:
            continue
        if "VECTOR" in upper_line and line.strip().startswith("###"):
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines).strip()


@lru_cache(maxsize=1)
def _load_command_reference() -> str:
    """Load authoritative ATC command documentation from repository root."""
    reference_path = Path(__file__).resolve().parents[2] / "ATC_COMMAND_REFERENCE.md"
    try:
        loaded = reference_path.read_text(encoding="utf-8").strip()
        return _filter_disabled_commands_from_reference(loaded)
    except (FileNotFoundError, OSError):
        return (
            "# ATC Command Reference (fallback)\n"
            "ATC <COMMAND> <CALLSIGN> [VALUE]\n"
            "- ATC ALTITUDE <CALLSIGN> <ALTITUDE>\n"
            "- ATC SPEED <CALLSIGN> <SPEED>\n"
            "- ATC HOLD <CALLSIGN>\n"
            "- ATC DIRECT <CALLSIGN> TO <WAYPOINT_OR_PROCEDURE>\n"
            "- ATC APPROACH <CALLSIGN>\n"
            "- ATC LAND <CALLSIGN> <RUNWAY_ID>\n"
            "- ATC RESUME <CALLSIGN>"
        )


def _get_available_commands(
    aircraft: AircraftObservation,
    active_runways: list[str],
    runway_occupancy: dict[str, str | None],
) -> list[str]:
    """
    Get available commands for an aircraft.

    Args:
        aircraft: AircraftObservation instance
        active_runways: List of active runway IDs
        runway_occupancy: Map of runway ID to occupying aircraft callsign

    Returns:
        List of command names
    """
    _ = aircraft  # Kept for API consistency and future extensions.
    commands = list(AVAILABLE_COMMANDS)

    # Filter LAND command based on runway availability
    if "LAND" in commands:
        # Only show LAND if there's an available (unoccupied) runway
        available = [r for r in active_runways if not runway_occupancy.get(r)]
        if not available:
            commands = [c for c in commands if c != "LAND"]

    return commands


def _format_aircraft_info(aircraft: AircraftObservation) -> str:
    """
    Format aircraft information for the prompt.

    Args:
        aircraft: AircraftObservation instance

    Returns:
        Formatted string with aircraft details
    """
    pos = aircraft.position
    motion = aircraft.motion
    intent = aircraft.intent

    info = (
        f"  - {aircraft.callsign}: {intent.state}\n"
        f"    Position: {pos.segment}, {pos.distance:.1f}km from center\n"
        f"    Altitude: {pos.altitude}ft (target: {pos.target_altitude}ft)\n"
        f"    Heading: {motion.heading:.0f}° (target: {motion.target_heading:.0f}°)\n"
        f"    Speed: {motion.speed}kts (target: {motion.target_speed}kts)"
    )

    if intent.assigned_runway:
        info += f"\n    Assigned Runway: {intent.assigned_runway}"

    if intent.distance_to_threshold is not None:
        info += f"\n    Distance to Threshold: {intent.distance_to_threshold:.1f}km"

    if intent.next_waypoint:
        info += f"\n    Next Waypoint: {intent.next_waypoint}"

    if aircraft.alerts:
        info += f"\n    ALERTS: {', '.join(aircraft.alerts)}"

    if aircraft.separation.closest_traffic:
        info += (
            f"\n    Nearest Traffic: {aircraft.separation.closest_traffic} "
            f"({aircraft.separation.distance:.1f}km, conflict: {aircraft.separation.conflict_risk})"
        )

    return info


def _format_available_commands(
    aircraft: AircraftObservation,
    active_runways: list[str],
    runway_occupancy: dict[str, str | None],
) -> str:
    """
    Format available commands for an aircraft.

    Args:
        aircraft: AircraftObservation instance
        active_runways: List of active runway IDs
        runway_occupancy: Map of runway ID to occupying aircraft callsign

    Returns:
        Formatted string with available commands
    """
    valid_cmds = _get_available_commands(aircraft, active_runways, runway_occupancy)

    cmd_strs = []
    for cmd in valid_cmds:
        if cmd == "ALTITUDE":
            cmd_strs.append(f"ATC ALTITUDE {aircraft.callsign} <altitude>")
        elif cmd == "SPEED":
            cmd_strs.append(f"ATC SPEED {aircraft.callsign} <speed>")
        elif cmd == "HOLD":
            cmd_strs.append(f"ATC HOLD {aircraft.callsign}")
        elif cmd == "DIRECT":
            cmd_strs.append(f"ATC DIRECT {aircraft.callsign} TO <waypoint_or_procedure>")
        elif cmd == "APPROACH":
            cmd_strs.append(f"ATC APPROACH {aircraft.callsign}")
        elif cmd == "LAND":
            available = [r for r in active_runways if not runway_occupancy.get(r)]
            runway_hint = available[0] if available else "<runway_id>"
            cmd_strs.append(f"ATC LAND {aircraft.callsign} {runway_hint}")
        elif cmd == "GO_AROUND":
            cmd_strs.append(f"ATC GO_AROUND {aircraft.callsign}")
        elif cmd == "RESUME":
            cmd_strs.append(f"ATC RESUME {aircraft.callsign}")

    return f"  {aircraft.callsign}:\n    " + "\n    ".join(cmd_strs)


def generate_atc_prompt(observation: ATCObservation) -> str:
    """
    Generate an ATC prompt for LLM-based control.

    Args:
        observation: ATCObservation from the simulation environment

    Returns:
        Formatted prompt string for the LLM
    """
    lines = []

    # System instruction
    lines.append("SYSTEM: You are an Air Traffic Controller.")
    lines.append("")

    # Current traffic overview
    lines.append("CURRENT TRAFFIC:")
    if not observation.aircraft:
        lines.append("  No aircraft in sector.")
    else:
        for ac in observation.aircraft:
            lines.append(_format_aircraft_info(ac))
    lines.append("")

    # Airport status
    lines.append("AIRPORT STATUS:")
    lines.append(
        f"  Active Runways: {', '.join(observation.airport_status.active_runways) or 'None'}"
    )
    lines.append(
        f"  Wind: {observation.airport_status.wind.heading}° at {observation.airport_status.wind.speed}kts"
    )
    if observation.airport_status.runway_occupancy:
        occ_parts = []
        for runway, occupant in observation.airport_status.runway_occupancy.items():
            if occupant:
                occ_parts.append(f"{runway} (occupied by {occupant})")
            else:
                occ_parts.append(f"{runway} (available)")
        lines.append(f"  Runway Occupancy: {', '.join(occ_parts)}")
    lines.append("")

    # Available commands by aircraft
    lines.append("AVAILABLE COMMANDS:")
    for ac in observation.aircraft:
        cmd_section = _format_available_commands(
            ac,
            observation.airport_status.active_runways,
            observation.airport_status.runway_occupancy,
        )
        lines.append(cmd_section)
    lines.append("")

    # Priority notices
    priority_lines = []

    # Low fuel aircraft
    low_fuel = [ac for ac in observation.aircraft if "low_fuel" in ac.alerts]
    if low_fuel:
        priority_lines.append("LOW FUEL AIRCRAFT:")
        for ac in low_fuel:
            priority_lines.append(
                f"  - {ac.callsign}: {ac.position.altitude}ft, {ac.position.distance:.1f}km out"
            )
        priority_lines.append("")

    # Critical emergency
    emergencies = [
        ac for ac in observation.aircraft if "critical_emergency" in ac.alerts
    ]
    if emergencies:
        priority_lines.append("EMERGENCY AIRCRAFT:")
        for ac in emergencies:
            priority_lines.append(
                f"  - {ac.callsign}: CRITICAL - Vector to nearest runway immediately"
            )
        priority_lines.append("")

    # High conflict risk
    high_conflict = [
        ac for ac in observation.aircraft if ac.separation.conflict_risk == "high"
    ]
    if high_conflict:
        priority_lines.append("COLLISION AVOIDANCE REQUIRED:")
        for ac in high_conflict:
            priority_lines.append(
                f"  - {ac.callsign} with {ac.separation.closest_traffic}: "
                f"Only {ac.separation.distance:.1f}km separation!"
            )
        priority_lines.append("")

    # Medium conflict risk
    medium_conflict = [
        ac for ac in observation.aircraft if ac.separation.conflict_risk == "medium"
    ]
    if medium_conflict:
        priority_lines.append("CAUTION - PROXIMITY WARNING:")
        for ac in medium_conflict:
            priority_lines.append(
                f"  - {ac.callsign} with {ac.separation.closest_traffic}: "
                f"{ac.separation.distance:.1f}km separation"
            )
        priority_lines.append("")

    if priority_lines:
        lines.append("PRIORITY NOTICES:")
        lines.extend(priority_lines)

    # Response instruction (command reference aligned)
    lines.append("")
    lines.append("ATC COMMAND REFERENCE (for output format):")
    lines.append("- ATC ALTITUDE <CALLSIGN> <ALTITUDE>")
    lines.append("- ATC SPEED <CALLSIGN> <SPEED>")
    lines.append("- ATC HOLD <CALLSIGN>")
    lines.append("- ATC DIRECT <CALLSIGN> TO <WAYPOINT_OR_PROCEDURE>")
    lines.append("- ATC APPROACH <CALLSIGN>")
    lines.append("- ATC LAND <CALLSIGN> <RUNWAY_ID>")
    lines.append("- ATC RESUME <CALLSIGN>")
    lines.append("")
    lines.append("Only issue commands that appear in AVAILABLE COMMANDS.")
    lines.append("Commands must use exact callsigns from CURRENT TRAFFIC.")
    lines.append("")
    lines.append("AUTHORITATIVE ATC COMMAND REFERENCE:")
    lines.append(_load_command_reference())

    return "\n".join(lines)
