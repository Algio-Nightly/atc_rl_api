# ATC Reward Function Specification

This document details the reward structure used to evaluate and train Air Traffic Control agents in this environment. The reward function is a **Weighted Sum** of five distinct rubrics, each focusing on a different aspect of ATC operations.

## Master Weighting (ATCRubric)
The final reward per step is calculated as:
`Total Reward = Σ (Weight_i * Rubric_i)`

| Rubric | Weight | Focus Area |
| :--- | :--- | :--- |
| **Safety** | 35% | Collision avoidance and aircraft separation. |
| **Efficiency** | 30% | Timely landings, fuel management, and mission progress. |
| **Compliance** | 15% | Command validity, redundancy control, and procedure adherence. |
| **Departure** | 15% | Ground management, taxi efficiency, and takeoff success. |
| **Format** | 5% | Syntactic correctness of the natural language output. |

---

## 1. Safety Rubric (35%)
Safety is the highest priority. Penalties in this section are usually the most severe.

| Event | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| Collision | Penalty | -10.0 | Triggered if aircraft proximity < 0.3km and altitude difference < 300ft. |
| Runway Incursion | Penalty | -10.0 | Landing on a runway occupied by another aircraft. |
| Fuel Exhaustion | Penalty | -10.0 | Aircraft runs out of fuel. |
| Near Miss | Penalty | -5.0 | Proximity < 5.0km and altitude < 1000ft (but not a collision). |
| Separation Violation | Penalty | -2.0 | Violation of standard ATC separation minima. |
| Conflict (High) | Penalty | -0.5 | Conflict risk evaluated by the simulation engine as "high". |

---

## 2. Efficiency Rubric (30%)
Encourages the agent to process traffic quickly and reach objectives.

| Event | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| Landing Success | Reward | +5.0 | Aircraft successfully lands on its assigned runway. |
| STAR Completion | Reward | +2.0 | Aircraft enters the ILS or Final Approach Segment. |
| Waypoint Reached | Reward | +0.5 | Reaching a non-terminal waypoint in the flight plan. |
| Go-Around | Penalty | -3.0 | Aborting a landing after being established on approach. |
| Time Penalty | Penalty | -0.01 | Per aircraft, per step. Prevents "doing nothing" to avoid penalties. |
| Holding Penalty | Penalty | -0.5 | Per minute spent in a holding pattern beyond 5 minutes. |

---

## 3. Compliance Rubric (15%)
Enforces correct command usage and procedure adherence.

### Dynamic Control Logic (New)
To prevent agents from spamming actions, the Compliance rubric uses dynamic scaling:

*   **Diminishing Validity Reward**: A correctly formatted command starts at `+0.1`, but decays by `-0.02` every time it is repeated for the same aircraft (minimum `+0.01`).
*   **Exponential Redundancy Penalty**: Repeating commands or toggling between two states (e.g., ALT 5000 -> ALT 4000 -> ALT 5000) triggers a penalty of `-0.05 * (1.1^frequency)`.
*   **No-Op Penalty**: Issuing a command that changes nothing (e.g., target altitude matches current altitude) triggers a penalty of `-0.1 * (1.2^frequency)`.

### Standard Compliance
| Event | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| Valid Command | Reward | +0.1 | Base reward for any syntactically valid and non-redundancy command. |
| Command Rejected | Penalty | -0.5 | Pilot rejects command (e.g., speed too fast for flap configuration). |
| Glide Slope | Reward | +0.2 | Staying within 500ft of target approach altitude during landing. |
| Airspace Exit | Penalty | -5.0 | Aircraft climbs above 45,000ft or descends below 0ft inappropriately. |

---

## 4. Departure Rubric (15%)
Covers the "Ground" and "Tower" control tasks.

| Event | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| Takeoff Success | Reward | +5.0 | Aircraft successfully transitions from takeoff roll to climb out. |
| Taxi Started | Reward | +1.0 | Aircraft moves from "On Gate" to a "Taxiing" state. |
| Taxi Delay | Penalty | -0.5 | Per minute spent taxiing beyond the 3-minute threshold. |
| Runway Occupancy | Penalty | -0.3 | Keeping a departure on the runway (Line Up and Wait) for too long. |

---

## 5. Format Rubric (5%)
A low-weight rubric to ensure the LLM follows the "natural language" prompt format.

| Event | Type | Value | Description |
| :--- | :--- | :--- | :--- |
| Well Formed | Reward | +0.05 | Prefix matches `ATC ` and command length is between 10-100 characters. |
| Malformed | Penalty | -0.1 | Failure to include the `ATC ` prefix or garbage output. |
