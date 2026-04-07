# ATC Command Reference

This document details the manual commands you can type into the server terminal (or send via WebSocket string payloads) to control aircraft in the simulation.

## Command Format
All commands follow a standardized space-separated format:
`ATC <COMMAND> <CALLSIGN> [VALUE]`

*   **ATC**: Required prefix.
*   **COMMAND**: The specific action (e.g., VECTOR, ALTITUDE).
*   **CALLSIGN**: The unique identifier of the aircraft (e.g., UA123).
*   **VALUE**: Optional parameter required by some commands (e.g., Heading, Altitude).

---

## Radar Symbology & Range

The simulation uses a high-fidelity radar display with a **45 KM** radius workspace.

- **Outer Rings**: 10 KM, 20 KM, 30 KM, and the **45 KM boundary ring**.
- **IAF (Initial Approach Fix)**: Represented as a **Purple Diamond**. (Target: 4000ft / 210kts).
- **FAF (Final Approach Fix)**: Represented as an **Orange Hexagon/Cross**. (Target: 2000ft / 180kts).
- **Sequence Constraints**: Aircraft will **NOT** advance to the next waypoint in a STAR unless they are within **200 ft** of the current target altitude.

---

## Navigation Commands

### 1. Vector (Heading)
Sets a new target heading for the aircraft.
*   **Syntax**: `ATC VECTOR <CALLSIGN> <HEADING>`
*   **Value**: Heading in degrees (0-359).
*   **Example**: `ATC VECTOR UA123 270` (Turns aircraft to West)

### 2. Direct To
Bypasses current route waypoints and flies directly to a specific fix.
*   **Syntax**: `ATC DIRECT_TO <CALLSIGN> <WAYPOINT_NAME>`
*   **Value**: Name of the waypoint (e.g., IAF-RWY_1).
*   **Example**: `ATC DIRECT_TO UA123 POM`

### 3. Hold
Instructs the aircraft to enter a holding pattern at its current position.
*   **Syntax**: `ATC HOLD <CALLSIGN>`
*   **Example**: `ATC HOLD UA123`

### 4. Resume
Resumes standard STAR/Route navigation (cancels Vectors or Holds).
*   **Syntax**: `ATC RESUME <CALLSIGN>`
*   **Example**: `ATC RESUME UA123`

---

## Flight Profile Commands

### 5. Altitude
Changes the aircraft's target altitude.
*   **Syntax**: `ATC ALTITUDE <CALLSIGN> <ALTITUDE>`
*   **Value**: Altitude in feet.
*   **Example**: `ATC ALTITUDE UA123 5000`

### 6. Speed
Changes the aircraft's target airspeed.
*   **Syntax**: `ATC SPEED <CALLSIGN> <SPEED>`
*   **Value**: Speed in knots.
*   **Example**: `ATC SPEED UA123 210`

---

## Arrival Procedures

### 7. Approach
Immediate transition to Final Approach logic. Aircraft will steer towards the runway centerline.
*   **Syntax**: `ATC APPROACH <CALLSIGN>`
*   **Example**: `ATC APPROACH UA123`

### 8. Land (Queued)
Clears aircraft for landing. **Aircraft will complete its current STAR route** and automatically trigger the approach logic once it reaches the **IAF**.
*   **Syntax**: `ATC LAND <CALLSIGN> <RUNWAY_ID>`
*   **Example**: `ATC LAND UA123 RWY_1`

---

## Notes for Users
1.  **Case Sensitivity**: The parser automatically converts commands and callsigns to uppercase.
2.  **Real-time Updates**: These commands are processed immediately by the simulation engine and reflected on the Radar visualizer.
3.  **Error Handling**: If a command is malformed, you will see an `[ATC Parser Error]` in the terminal output.
