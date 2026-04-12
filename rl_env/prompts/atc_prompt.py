"""ATC prompt generator for LLM-based control."""

from functools import lru_cache
from pathlib import Path

from rl_env.models import ATCObservation, AircraftObservation


@lru_cache(maxsize=1)
def _load_command_reference() -> str:
    """Load authoritative ATC command documentation from repository root."""
    reference_path = Path(__file__).resolve().parents[2] / "ATC_COMMAND_REFERENCE.md"
    try:
        return reference_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return (
            "# ATC Command Reference (fallback)\n"
            "ATC <COMMAND> <CALLSIGN> [VALUE]\n"
            "- ATC ALTITUDE <CALLSIGN> <ALTITUDE>\n"
            "- ATC SPEED <CALLSIGN> <SPEED>\n"
            "- ATC HOLD <CALLSIGN>\n"
            "- ATC DIRECT <CALLSIGN> TO <WAYPOINT_OR_PROCEDURE>\n"
            "- ATC LAND <CALLSIGN> <RUNWAY_ID>\n"
            "- ATC RESUME <CALLSIGN>"
        )


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

    if intent.state == "ENROUTE_CLEARED":
        info += f"\n    ** CLEARED FOR LANDING **"

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





def generate_atc_prompt(observation: ATCObservation) -> str:
    """
    Generate an ATC prompt for LLM-based control.

    Args:
        observation: ATCObservation from the simulation environment

    Returns:
        Formatted prompt string for the LLM
    """
    lines = []

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

    # Response instruction
    lines.append("")
    lines.append("Only issue commands that appear in the AUTHORITATIVE ATC COMMAND REFERENCE below.")
    lines.append("Commands must use exact callsigns from CURRENT TRAFFIC.")
    lines.append("")
    lines.append("AUTHORITATIVE ATC COMMAND REFERENCE:")
    lines.append(_load_command_reference())

    return "\n".join(lines)
