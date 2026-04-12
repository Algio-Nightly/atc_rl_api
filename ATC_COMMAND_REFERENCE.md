# ATC Command Reference

This document details the manual commands recognize by the Air Traffic Control system to manage aircraft safely and efficiently.

## Command Format
All commands follow a standardized space-separated format:
`ATC <COMMAND> [CALLSIGN] [VALUE]`

*   **ATC**: Required prefix.
*   **COMMAND**: The specific action (e.g., ALTITUDE, LAND).
*   **CALLSIGN**: The unique identifier of the aircraft (e.g., UA123). Optional for sectoral commands like PASS.
*   **VALUE**: Optional parameter required by some commands (e.g., Altitude, Runway ID).

---

## Sectoral Commands

### 1. Pass
Indicates that the controller has reviewed the sector and no action is currently required for any aircraft.
*   **Syntax**: `ATC PASS`
*   **Example**: `ATC PASS`
*   **Note**: Use this to signify intentional monitoring without intervention. It avoids redundant command penalties.

---

## Navigation & Routing

### 2. Direct To
Bypasses current route waypoints and flies directly to a specific fix or enters a named procedure.
*   **Syntax**: `ATC DIRECT <CALLSIGN> TO <WAYPOINT_OR_PROCEDURE>`
*   **Value**: Name of a Waypoint (e.g., `POM`) or a Procedural Alias (e.g., `SUTRA_1A`).
*   **Example**: `ATC DIRECT UA123 TO SUTRA_1A`
*   **Note**: 
    - Waypoint and Procedure names **must NOT contain spaces**. Use underscores (e.g., `POOMA_1A`) instead.
    - If a **Procedure** (STAR or SID) is specified, the aircraft will immediately start flying that route from its current position.
    - If a **Waypoint** is part of the current active procedure, the aircraft flies there and then resumes the rest of the route.

### 3. Hold
Instructs the aircraft to enter a holding pattern at its current position.
*   **Syntax**: `ATC HOLD <CALLSIGN>`
*   **Example**: `ATC HOLD UA123`

### 4. Resume
Resumes standard STAR/Route navigation (cancels manual Altitude or Speed overrides and resumes waypoint-based steering).
*   **Syntax**: `ATC RESUME <CALLSIGN>`
*   **Example**: `ATC RESUME UA123`

---

## Flight Profile Overrides

### 5. Altitude
Changes the aircraft's target altitude.
*   **Syntax**: `ATC ALTITUDE <CALLSIGN> <ALTITUDE>`
*   **Value**: Altitude in feet. Range: 100 - 45,000 ft.
*   **Example**: `ATC ALTITUDE UA123 5000`
*   **Note**: This creates a **Manual Override**. The aircraft will maintain this altitude until instructed otherwise or until the **RESUME** command is used.

### 6. Speed
Changes the aircraft's target airspeed.
*   **Syntax**: `ATC SPEED <CALLSIGN> <SPEED>`
*   **Value**: Speed in knots. Range: 140 - 450 kts.
*   **Example**: `ATC SPEED UA123 210`
*   **Note**: This creates a **Manual Override**. The aircraft will maintain this speed until instructed otherwise or until the **RESUME** command is used.

---

## Arrival Procedures

### 7. Land (Queued Approach)
Clears an aircraft for landing on a specific runway. **Aircraft will complete its current STAR route** and automatically begin the final approach sequence once it reaches the **IAF**.
*   **Syntax**: `ATC LAND <CALLSIGN> <RUNWAY_ID>`
*   **Example**: `ATC LAND UA123 RWY_1`
*   **Note**: Once cleared, the aircraft state changes to `ENROUTE_CLEARED`. Do not re-issue LAND once in this state.

---

## Departure & Ground Operations

### 8. Taxi
Clears an aircraft to push back and taxi to the active departure runway.
*   **Syntax**: `ATC TAXI <CALLSIGN> TO <RUNWAY_ID>`
*   **Example**: `ATC TAXI UA123 TO RWY_1`
*   **Note**: Aircraft must be in the `ON_GATE` state. It will automatically move to the runway threshold.

### 9. Takeoff
Clears an aircraft at the threshold for departure.
*   **Syntax**: `ATC TAKEOFF <CALLSIGN>`
*   **Example**: `ATC TAKEOFF UA123`
*   **Note**: 
    - If at the threshold (`HOLDING_SHORT`), the aircraft will enter the runway, align (30s), and then begin the takeoff roll.
    - Rotation occurs at **160 knots**, followed by a climb-out sequence following the assigned SID.

---

## Notes for Users
1.  **Case Sensitivity**: The parser is case-insensitive (converts everything to uppercase).
2.  **Telemetry Logic**: All commands are logged immediately and visible to all connected clients.
3.  **Conflict Prevention**: Controllers must maintain minimum separation intervals. Commands that would lead to unsafe conditions may result in simulator events or penalties.
