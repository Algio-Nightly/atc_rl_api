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


### 2. Direct To
Bypasses current route waypoints and flies directly to a specific fix or enters a named procedure.
*   **Syntax**: `ATC DIRECT <CALLSIGN> TO <WAYPOINT_OR_PROCEDURE>`
*   **Value**: Name of a Waypoint (e.g., `POM`) or a Procedural Alias (e.g., `SUTRA_1A`).
*   **Example**: `ATC DIRECT UA123 TO SUTRA_1A`
*   **Note**: 
    - **No Spaces**: Waypoint and Procedure names **must NOT contain spaces**. Use underscores (e.g., `POOMA_1A`) instead.
    - If a **Procedure** (STAR or SID) is specified, the aircraft will immediately start flying that route from the first waypoint.
    - If a **Waypoint** is part of the current active procedure, the aircraft flies there and then correctly resumes the rest of the route (skipping middle waypoints).

### 3. Hold
Instructs the aircraft to enter a holding pattern at its current position.
*   **Syntax**: `ATC HOLD <CALLSIGN>`
*   **Example**: `ATC HOLD UA123`

### 4. Resume
Resumes standard STAR/Route navigation (cancels manual Altitude or Speed overrides and resumes waypoint-based steering).
*   **Syntax**: `ATC RESUME <CALLSIGN>`
*   **Example**: `ATC RESUME UA123`

---

## Flight Profile Commands

### 5. Altitude
Changes the aircraft's target altitude.
*   **Syntax**: `ATC ALTITUDE <CALLSIGN> <ALTITUDE>`
*   **Value**: Altitude in feet. Range: 100 - 45,000 ft.
*   **Example**: `ATC ALTITUDE UA123 5000`
*   **Note**: This creates a **Manual Override**. The aircraft will maintain this altitude even if its current STAR route prescribes something else. Use the **RESUME** command to return to procedural altitudes.

### 6. Speed
Changes the aircraft's target airspeed.
*   **Syntax**: `ATC SPEED <CALLSIGN> <SPEED>`
*   **Value**: Speed in knots. Range: 140 - 450 kts.
*   **Example**: `ATC SPEED UA123 210`
*   **Note**: This creates a **Manual Override**. The aircraft will maintain this speed even if its current STAR route prescribes something else. Use the **RESUME** command to return to procedural speeds.

---

## Arrival Procedures


### 8. Land (Queued)
Clears aircraft for landing. **Aircraft will complete its current STAR route** and automatically trigger the approach logic once it reaches the **IAF**.
*   **Syntax**: `ATC LAND <CALLSIGN> <RUNWAY_ID>`
*   **Example**: `ATC LAND UA123 RWY_1`

---

## Departure & Ground Operations

### 9. Taxi
Clears an aircraft to push back from its terminal stand and taxi to the runway.
*   **Syntax**: `ATC TAXI <CALLSIGN> TO <RUNWAY_ID>`
*   **Example**: `ATC TAXI UA123 TO RWY_1`
*   **Note**: Aircraft must be in the `ON_GATE` state. It will automatically move at 20kts to the runway threshold.

### 10. Takeoff (Automated Line-up & Roll)
Clears an aircraft for departure. This is the primary command for all departing aircraft at the threshold.
*   **Syntax**: `ATC TAKEOFF <CALLSIGN>`
*   **Example**: `ATC TAKEOFF UA123`
*   **Note**: 
    - **Step 1 (Auto-Alignment)**: If the aircraft is at the threshold (`HOLDING_SHORT`), it will automatically enter the runway and wait for **30 seconds** to align.
    - **Step 2 (Takeoff Roll)**: Once aligned, the aircraft automatically begins its takeoff roll, rotating at **160 knots**.
    - If the aircraft is already aligned (`LINE_UP`), it begins the takeoff roll immediately.

---

## Notes for Users
1.  **Case Sensitivity**: The parser automatically converts commands and callsigns to uppercase.
2.  **Real-time Updates**: These commands are processed immediately by the simulation engine and reflected on the Radar visualizer.
3.  **Error Handling**: If a command is malformed, you will see an `[ATC Parser Error]` in the terminal output.
