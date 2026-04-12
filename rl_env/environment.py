"""ATC RL Environment - Main OpenEnv interface for ATC simulation."""

import math
import uuid
from typing import Optional, Any

from openenv_core import Environment

from core.engine import SimulationEngine
from rl_env.models import (
    ATCAction,
    ATCObservation,
    ATCState,
    AircraftObservation,
    Position,
    Motion,
    Intent,
    Separation,
    AirportStatus,
    Metrics,
    Wind,
    TimingStats,
    SafetyMetrics,
)
from rl_env.rubrics import ATCRubric
from rl_env.parsers import parse, ParseError


# Task configuration constants
TASK_CONFIGS = {
    "single_approach": {
        "aircraft_count": 1,
        "spawn_distance_km": 15.0,
        "gates": ["N"],
        "ac_types": ["B737"],
        "weight_classes": ["Heavy"],
    },
    "single_departure": {
        "aircraft_count": 1,
        "spawn_distance_km": 0,
        "gates": ["G1"],
        "ac_types": ["B737"],
        "weight_classes": ["Medium"],
        "is_departure": True,
    },
    "traffic_pattern": {
        "aircraft_count": 4,
        "spawn_distance_km": 20.0,
        "spawn_interval_sec": 20.0,
        "gates": ["N", "S", "E", "W"],
        "ac_types": ["B737", "A320", "B777", "E190"],
        "weight_classes": ["Heavy", "Medium", "Light"],
    },
    "multi_departure": {
        "aircraft_count": 3,
        "spawn_distance_km": 0,
        "gates": ["G1", "G2", "G3"],
        "ac_types": ["B737", "A320", "E190"],
        "weight_classes": ["Medium", "Medium", "Light"],
        "is_departure": True,
    },
    "storm_traffic": {
        "aircraft_count": 10,
        "spawn_distance_km": 25.0,
        "spawn_interval_sec": 15.0,
        "gates": ["N", "S", "E", "W", "N", "S", "E", "W", "N", "S"],
        "ac_types": ["B737", "A320", "B777", "E190", "A350"],
        "weight_classes": ["Heavy", "Medium", "Light", "Heavy", "Medium"],
    },
    "mixed_operations": {
        "aircraft_count": 6,
        "spawn_distance_km": 20.0,
        "gates": ["N", "S", "G1", "G2", "E", "G3"],
        "ac_types": ["B737", "A320", "B777", "E190", "A350", "B737"],
        "weight_classes": ["Heavy", "Medium", "Heavy", "Light", "Medium", "Medium"],
        "is_mixed": True,
    },
}

# Segment labels for position calculation
SEGMENTS_LABELS = [
    "North",
    "North-East",
    "East",
    "South-East",
    "South",
    "South-West",
    "West",
    "North-West",
]

# Default airport code
DEFAULT_AIRPORT = "VOCB"


class ATCEnv(Environment):
    """
    ATC Reinforcement Learning Environment using Meta OpenEnv.

    Integrates simulation engine, command parser, rubrics, and observation generation
    to provide a complete RL interface for ATC training scenarios.
    """

    def __init__(self, airport_code: str = DEFAULT_AIRPORT):
        """
        Initialize the ATC environment.

        Args:
            airport_code: ICAO airport code to use (default: HEAT)
        """
        super().__init__()
        self.airport_code = airport_code
        self.engine: Optional[SimulationEngine] = None
        self.rubric = ATCRubric()
        self.episode_id: Optional[str] = None
        self.step_count: int = 0
        self.task_name: Optional[str] = None
        self.cumulative_reward: float = 0.0
        self.command_history: dict[
            str, list[str]
        ] = {}  # For redundant command detection
        self._previous_observation: Optional[ATCObservation] = None
        self._initial_aircraft_count: int = 0
        self._pending_spawns: list[dict[str, Any]] = []
        self._planes_landed: int = 0

    def reset(
        self,
        seed: Optional[int] = None,
        task: str = "single_approach",
        skip_spawn: bool = False,
    ) -> tuple[ATCObservation, dict]:
        """
        Reset the simulation to initial state for a new episode.

        Args:
            seed: Random seed for reproducibility (optional)
            task: Task configuration name (single_approach, traffic_pattern, storm_traffic)
            skip_spawn: If True, skip aircraft spawning (task classes spawn aircraft themselves)

        Returns:
            Tuple of (observation, info dict)
        """
        super().reset(seed=seed)

        # Initialize new episode
        self.engine = SimulationEngine()
        self.episode_id = f"ep_{uuid.uuid4().hex[:8]}"
        self.step_count = 0
        self.cumulative_reward = 0.0
        self.rubric = ATCRubric()
        self.command_history = {}
        self._previous_observation = None
        self._pending_spawns = []
        self._planes_landed = 0

        # Load airport configuration directly from JSON
        config = self._load_airport_config(self.airport_code)
        self.engine.load_airport(config)

        # Get task configuration (default to single_approach if not found)
        task_config = TASK_CONFIGS.get(task, TASK_CONFIGS["single_approach"])
        self.task_name = task

        if not skip_spawn:
            self._spawn_aircraft_for_task(task_config)

        observation = self._build_observation()
        info = {"episode_id": self.episode_id, "task_name": self.task_name}

        self._previous_observation = observation
        self._initial_aircraft_count = len(self.engine.aircrafts) + len(self._pending_spawns)

        return (observation, info)

    def _spawn_aircraft_for_task(self, task_config: dict) -> None:
        """
        Spawn aircraft according to task configuration.

        Args:
            task_config: Dictionary containing aircraft_count, spawn_distance_km, gates, etc.
        """
        if task_config.get("is_departure"):
            self._spawn_aircraft_for_departure(task_config)
            return

        if task_config.get("is_mixed"):
            arrival_gates = [g for g in task_config["gates"] if not g.startswith("G")]
            departure_gates = [g for g in task_config["gates"] if g.startswith("G")]

            if arrival_gates:
                arrival_config = {
                    "aircraft_count": len(arrival_gates),
                    "spawn_distance_km": task_config["spawn_distance_km"],
                    "gates": arrival_gates,
                    "ac_types": task_config["ac_types"][: len(arrival_gates)],
                    "weight_classes": task_config["weight_classes"][
                        : len(arrival_gates)
                    ],
                }
                self._spawn_arrivals(arrival_config)

            if departure_gates:
                departure_config = {
                    "aircraft_count": len(departure_gates),
                    "spawn_distance_km": 0,
                    "gates": departure_gates,
                    "ac_types": task_config["ac_types"][len(arrival_gates) :],
                    "weight_classes": task_config["weight_classes"][
                        len(arrival_gates) :
                    ],
                    "is_departure": True,
                }
                self._spawn_aircraft_for_departure(departure_config)
            return

        self._spawn_arrivals(task_config)

    def _spawn_arrivals(self, task_config: dict) -> None:
        """Spawn arrival aircraft in the airspace."""
        import random

        aircraft_count = task_config["aircraft_count"]
        spawn_distance_km = task_config["spawn_distance_km"]
        spawn_interval_sec = float(task_config.get("spawn_interval_sec", 0.0))
        ac_types = task_config["ac_types"]
        weight_classes = task_config["weight_classes"]

        all_gates = list(task_config["gates"])
        upwind_gates = self._select_upwind_gates()
        preferred_gates = [g for g in all_gates if g in upwind_gates]
        if not preferred_gates:
            preferred_gates = list(all_gates)

        # Avoid pathological same-gate spawning when wind leaves only one preferred gate.
        # Fill with remaining configured gates before cycling.
        gates = list(preferred_gates)
        if len(gates) < aircraft_count:
            for gate in all_gates:
                if gate not in gates:
                    gates.append(gate)
                if len(gates) >= aircraft_count:
                    break

        for i in range(aircraft_count):
            callsign = f"RL{i + 1:03d}"
            gate = gates[i % len(gates)]
            ac_type = ac_types[i % len(ac_types)]
            weight_class = weight_classes[i % len(weight_classes)]

            base_altitude = 8000 + (i * 1000)
            altitude = min(base_altitude, 15000)

            if self.engine.config and gate in self.engine.config.gates:
                gate_pos = self.engine.config.gates[gate]
                dx = 0 - gate_pos.x
                dy = 0 - gate_pos.y
                heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
            else:
                heading = None

            spawn_payload = {
                "callsign": callsign,
                "ac_type": ac_type,
                "weight_class": weight_class,
                "gate": gate,
                "altitude": altitude,
                "heading": heading,
                "speed": 250,
            }

            if i == 0 or spawn_interval_sec <= 0:
                self.engine.add_aircraft(**spawn_payload)
            else:
                self.add_pending_spawn(
                    spawn_time=spawn_interval_sec * i,
                    method="add_aircraft",
                    payload=spawn_payload,
                )

    def _process_pending_spawns(self) -> None:
        """Spawn scheduled arrivals once simulation time reaches spawn_time."""
        if not self._pending_spawns or self.engine is None:
            return

        current_time = self.engine.simulation_time
        ready_spawns = [
            item for item in self._pending_spawns if item["spawn_time"] <= current_time
        ]
        if not ready_spawns:
            return

        self._pending_spawns = [
            item for item in self._pending_spawns if item["spawn_time"] > current_time
        ]
        for item in ready_spawns:
            method_name = item.get("method", "add_aircraft")
            payload = item["payload"]
            
            method = getattr(self.engine, method_name)
            method(**payload)

    def add_pending_spawn(
        self, spawn_time: float, method: str, payload: dict[str, Any]
    ) -> None:
        """
        Schedule an aircraft to be spawned at a future simulation time.

        Args:
            spawn_time: Simulation time at which to spawn
            method: Name of the engine method to call ('add_aircraft' or 'spawn_departure')
            payload: Keyword arguments for the engine method
        """
        self._pending_spawns.append(
            {"spawn_time": spawn_time, "method": method, "payload": payload}
        )

    def _select_upwind_gates(self) -> list[str]:
        """Select gates that face into the headwind for arrival spawning.

        Returns gates where the approach heading (from gate to center) is within
        ±90° of the wind heading, meaning aircraft would approach into the wind.
        Falls back to all gates if wind_heading is 0 or undefined.
        """
        if not self.engine or not self.engine.config:
            return (
                list(self.engine.config.gates.keys())
                if self.engine and self.engine.config
                else []
            )

        wind_heading = getattr(self.engine, "wind_heading", 0.0)
        if wind_heading == 0.0 or wind_heading is None:
            # No wind or undefined wind — use all gates
            return list(self.engine.config.gates.keys())

        upwind_gates = []
        for gate_name, gate_pos in self.engine.config.gates.items():
            # Calculate bearing from gate to center (0,0)
            dx = 0 - gate_pos.x
            dy = 0 - gate_pos.y
            approach_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360

            # Check if approach heading faces into the wind (within ±90°)
            diff = (approach_heading - wind_heading + 180) % 360 - 180
            if abs(diff) < 90:
                upwind_gates.append(gate_name)

        # Fallback: if no upwind gates found, use all gates
        if not upwind_gates:
            return list(self.engine.config.gates.keys())

        return upwind_gates

    def _spawn_aircraft_for_departure(self, task_config: dict) -> None:
        """Spawn departure aircraft on the ground at terminal gates."""
        aircraft_count = task_config["aircraft_count"]
        gates = task_config["gates"]
        ac_types = task_config["ac_types"]
        weight_classes = task_config["weight_classes"]

        existing_count = len(self.engine.aircrafts)

        if self.engine.active_runways:
            runway_id = self.engine.active_runways[0]
        elif self.engine.config and self.engine.config.runways:
            runway_id = self.engine.config.runways[0].id
        else:
            runway_id = "RWY_1"

        spawn_interval_sec = float(task_config.get("spawn_interval_sec", 30.0))

        for i in range(aircraft_count):
            callsign = f"RL{existing_count + i + 1:03d}"
            ac_type = ac_types[i % len(ac_types)]
            gate = gates[i % len(gates)]

            terminal_gate_id = gate if gate.startswith("G") else None
            sid_gate = "N"

            payload = {
                "callsign": callsign,
                "ac_type": ac_type,
                "runway_id": runway_id,
                "gate_id": sid_gate,
                "terminal_gate_id": terminal_gate_id,
            }

            if i == 0 or spawn_interval_sec <= 0:
                self.engine.spawn_departure(**payload)
            else:
                self.add_pending_spawn(
                    spawn_time=spawn_interval_sec * i,
                    method="spawn_departure",
                    payload=payload,
                )

    def _load_airport_config(self, airport_code: str):
        import json
        from pathlib import Path

        airports_dir = Path(__file__).parent.parent / "airports"
        config_path = airports_dir / f"{airport_code.upper()}.json"

        if not config_path.exists():
            raise ValueError(f"Airport config not found: {config_path}")

        with open(config_path, "r") as f:
            data = json.load(f)

        return AirportConfigDirect(data)

    def step(self, action: ATCAction) -> tuple[ATCObservation, float, bool, bool, dict]:
        """
        Execute one step of the simulation.

        Args:
            action: ATCAction containing commands to execute

        Returns:
            Tuple of (observation, reward, done, truncated, info)
        """
        self.step_count += 1

        self._execute_commands(action)
        self._process_pending_spawns()

        self.engine.step(1.0)

        step_events = list(self.engine.event_buffer)

        # Track successful landings and departures
        for evt in step_events:
            if evt.get("type") in ("SUCCESSFUL_LANDING", "SUCCESSFUL_DEPARTURE"):
                self._planes_landed += 1

        observation = self._build_observation()

        reward = self.rubric.forward(action, observation, events=step_events)
        reward = max(-100.0, min(100.0, reward))
        self.cumulative_reward += reward

        done = self._check_terminal_conditions(observation)
        truncated = False

        info = {
            "episode_id": self.episode_id,
            "step_count": self.step_count,
            "task_name": self.task_name,
            "cumulative_reward": self.cumulative_reward,
            "events": step_events,
            "reward_breakdown": self._get_reward_breakdown(),
        }

        self._flush_aircraft_metrics()
        self._previous_observation = observation

        return (observation, reward, done, truncated, info)

    def _flush_aircraft_metrics(self) -> None:
        """
        Reset step-specific metrics on all aircraft to prepare for next step.
        """
        for ac in self.engine.aircrafts.values():
            ac.separation_warnings = 0
            ac.closest_proximity_km = 999.0
            ac.command_rejections.clear()

    def _execute_commands(self, action: ATCAction) -> None:
        """
        Parse and execute ATC commands.

        Args:
            action: ATCAction containing command strings
        """
        if not action.commands:
            return

        for cmd_str in action.commands:
            try:
                parsed = parse(cmd_str)
                # Handle batch parsing (returns list) or single command (returns dict)
                commands = parsed if isinstance(parsed, list) else [parsed]

                for cmd in commands:
                    self._execute_single_command(cmd)
            except ParseError as e:
                # Log parse error but continue with other commands
                self.engine.event_buffer.append(
                    {
                        "type": "PARSE_ERROR",
                        "msg": f"Failed to parse command: {e}",
                        "timestamp": time.time(),
                    }
                )
                continue

    def _execute_single_command(self, cmd: dict) -> None:
        """
        Execute a single parsed command on the simulation engine.

        Args:
            cmd: Parsed command dictionary
        """
        import time

        command = cmd.get("command", "").upper()
        callsign = cmd.get("callsign", "").upper()

        # Check if aircraft exists
        if callsign not in self.engine.aircrafts:
            self.engine.event_buffer.append(
                {
                    "type": "COMMAND_ERROR",
                    "msg": f"Aircraft '{callsign}' not found",
                    "timestamp": time.time(),
                }
            )
            return

        aircraft = self.engine.aircrafts[callsign]

        def reject(reason: str):
            aircraft.command_rejections.append(f"{command} (Rejected: {reason})")
            self.engine.event_buffer.append(
                {
                    "type": "COMMAND_ERROR",
                    "msg": f"COMMAND REJECTED: {callsign} {command} -> {reason}",
                    "timestamp": time.time(),
                }
            )

        if command == "ALTITUDE":
            altitude = cmd.get("altitude")
            if altitude is not None:
                aircraft.target_alt = float(altitude)
                self.engine.event_buffer.append(
                    {
                        "type": "ATC",
                        "msg": f"ALTITUDE: {callsign} -> {altitude}ft",
                        "timestamp": time.time(),
                    }
                )

        elif command == "SPEED":
            speed = cmd.get("speed")
            if speed is not None:
                aircraft.target_speed = float(speed)
                self.engine.event_buffer.append(
                    {
                        "type": "ATC",
                        "msg": f"SPEED: {callsign} -> {speed}kts",
                        "timestamp": time.time(),
                    }
                )

        elif command == "HOLD":
            waypoint = cmd.get("waypoint")
            altitude = cmd.get("altitude")
            aircraft.state = "HOLDING"
            if waypoint and self.engine.config:
                # Look up waypoint position
                search_term = waypoint.upper()
                found_wp = None
                for wp in self.engine.config.waypoints.values():
                    if (
                        wp.name and wp.name.upper() == search_term
                    ) or wp.id.upper() == search_term:
                        found_wp = wp.model_dump()
                        break
                if found_wp:
                    aircraft.holding_fix = {"x": found_wp["x"], "y": found_wp["y"]}
            if altitude is not None:
                aircraft.target_alt = float(altitude)
            self.engine.event_buffer.append(
                {
                    "type": "ATC",
                    "msg": f"HOLD: {callsign} holding",
                    "timestamp": time.time(),
                }
            )

        elif command == "DIRECT":
            waypoint = cmd.get("waypoint")
            if waypoint and self.engine.config:
                search_term = waypoint.upper()
                found_wp = None
                for wp in self.engine.config.waypoints.values():
                    if (
                        wp.name and wp.name.upper() == search_term
                    ) or wp.id.upper() == search_term:
                        found_wp = wp.model_dump()
                        break
                if found_wp:
                    aircraft.direct_to_wp = found_wp
                    aircraft.state = "ENROUTE"
                    self.engine.event_buffer.append(
                        {
                            "type": "ATC",
                            "msg": f"DIRECT: {callsign} -> {waypoint}",
                            "timestamp": time.time(),
                        }
                    )
                else:
                    reject(f"Waypoint {waypoint} not found")

        elif command == "LAND":
            runway = cmd.get("runway")
            if runway and self.engine.config:
                rw_id = runway.upper()
                target_rw = next(
                    (r for r in self.engine.config.runways if r.id == rw_id), None
                )
                if target_rw:
                    aircraft.target_runway_id = rw_id
                    aircraft.queued_landing = {
                        "runway_id": rw_id,
                        "threshold": {"x": target_rw.start.x, "y": target_rw.start.y},
                        "runway_heading": target_rw.heading,
                    }
                    # LAND is a queued clearance, not an immediate touchdown phase.
                    # Aircraft transitions to APPROACH/LANDING in aircraft.update()
                    # when it reaches the right procedure points.
                    self.engine.event_buffer.append(
                        {
                            "type": "ATC",
                            "msg": f"LAND: {callsign} queued for RWY {rw_id}",
                            "timestamp": time.time(),
                        }
                    )
                else:
                    reject(f"Runway {rw_id} not found")
            else:
                reject("Missing runway assignment")

        elif command == "TAXI":
            if aircraft.state != "ON_GATE":
                reject("Must be ON_GATE to taxi")
                return

            runway = cmd.get("runway")
            if runway and self.engine.config:
                rw_id = runway.upper()
                target_rw = next(
                    (r for r in self.engine.config.runways if r.id == rw_id), None
                )
                if target_rw:
                    aircraft.target_runway_id = rw_id
                    aircraft.runway_threshold = {
                        "x": target_rw.start.x,
                        "y": target_rw.start.y,
                    }
                    aircraft.runway_heading = target_rw.heading
                    aircraft.state = "TAXIING"
                    self.engine.event_buffer.append(
                        {
                            "type": "ATC",
                            "msg": f"TAXI: {callsign} to RWY {rw_id}",
                            "timestamp": time.time(),
                        }
                    )
                else:
                    reject(f"Runway {rw_id} not found")
            else:
                reject("Missing runway assignment")

        elif command == "TAKEOFF":
            if aircraft.state == "TAXIING":
                aircraft.queued_takeoff = True
                self.engine.event_buffer.append(
                    {
                        "type": "ATC",
                        "msg": f"QUEUED TAKEOFF: {callsign}",
                        "timestamp": time.time(),
                    }
                )
            elif aircraft.state == "HOLDING_SHORT":
                aircraft.state = "LINE_UP"
                aircraft.line_up_timer = 30.0
                if aircraft.target_runway_id:
                    self.engine.runway_status[aircraft.target_runway_id][
                        "occupied_by"
                    ] = callsign
                self.engine.event_buffer.append(
                    {
                        "type": "ATC",
                        "msg": f"CLEARED TAKEOFF: {callsign} (Aligning)",
                        "timestamp": time.time(),
                    }
                )
            elif aircraft.state == "LINE_UP":
                aircraft.state = "TAKEOFF_ROLL"
                self.engine.event_buffer.append(
                    {
                        "type": "ATC",
                        "msg": f"CLEARED TAKEOFF: {callsign}",
                        "timestamp": time.time(),
                    }
                )
            else:
                reject(f"Cannot takeoff from state {aircraft.state}")

        elif command == "RESUME":
            aircraft.state = "ENROUTE"
            aircraft.direct_to_wp = None
            self.engine.event_buffer.append(
                {
                    "type": "ATC",
                    "msg": f"RESUME: {callsign} resuming navigation",
                    "timestamp": time.time(),
                }
            )

    def _build_observation(self) -> ATCObservation:
        """
        Build ATCObservation from current engine state.

        Returns:
            ATCObservation Pydantic model
        """
        # Build airport status
        wind = Wind(
            heading=int(self.engine.wind_heading) % 360,
            speed=int(self.engine.wind_speed),
        )

        runway_occupancy = {}
        for r_id, status in self.engine.runway_status.items():
            runway_occupancy[r_id] = status.get("occupied_by")

        airport_status = AirportStatus(
            active_runways=list(self.engine.active_runways),
            runway_occupancy=runway_occupancy,
            wind=wind,
        )

        # Build aircraft observations
        aircraft_list = []
        for ac in self.engine.aircrafts.values():
            ac_obs = self._build_aircraft_observation(ac)
            aircraft_list.append(ac_obs)

        # Build metrics
        metrics = Metrics(
            simulation_time=round(self.engine.simulation_time, 1),
            planes_landed=self._planes_landed,
            planes_active=len(self.engine.aircrafts),
        )

        return ATCObservation(
            airport_status=airport_status,
            aircraft=aircraft_list,
            metrics=metrics,
        )

    def _build_aircraft_observation(self, ac) -> AircraftObservation:
        """
        Build AircraftObservation for a single aircraft.

        Args:
            ac: Aircraft object from the simulation engine

        Returns:
            AircraftObservation Pydantic model
        """
        import time

        # Calculate position
        distance = math.sqrt(ac.x**2 + ac.y**2)
        if ac.x == 0 and ac.y == 0:
            bearing = 0.0
        else:
            bearing = (90 - math.degrees(math.atan2(ac.y, ac.x))) % 360
        segment_idx = round(bearing / 45) % 8
        segment_name = SEGMENTS_LABELS[segment_idx]

        position = Position(
            segment=segment_name,
            distance=round(distance, 2),
            altitude=int(ac.altitude),
            target_altitude=int(ac.target_alt),
        )

        # Build motion
        motion = Motion(
            heading=round(ac.heading, 1),
            target_heading=round(ac.target_heading, 1),
            speed=int(ac.speed),
            target_speed=int(ac.target_speed),
        )

        # Build intent
        dist_to_thresh = None
        if ac.runway_threshold:
            tx, ty = ac.runway_threshold["x"], ac.runway_threshold["y"]
            dist_to_thresh = round(math.sqrt((tx - ac.x) ** 2 + (ty - ac.y) ** 2), 2)

        next_wp = (
            ac.active_star if hasattr(ac, "active_star") and ac.active_star else "None"
        )
        if hasattr(ac, "direct_to_wp") and ac.direct_to_wp:
            next_wp = ac.direct_to_wp.get("name", "Direct")

        # Map to observation-layer state: if aircraft is ENROUTE but has a
        # queued landing clearance, expose it as ENROUTE_CLEARED so the LLM
        # knows not to re-issue the LAND command.
        observable_state = ac.state
        if ac.state == "ENROUTE" and getattr(ac, "queued_landing", None):
            observable_state = "ENROUTE_CLEARED"
        # Normalize engine-internal crash variants to the schema-valid "CRASHED"
        elif ac.state.startswith("CRASHED"):
            observable_state = "CRASHED"

        intent = Intent(
            state=observable_state,
            assigned_runway=ac.target_runway_id,
            distance_to_threshold=dist_to_thresh,
            next_waypoint=next_wp,
        )

        # Build alerts
        alerts = []
        if hasattr(ac, "fuel_level") and ac.fuel_level < 10:
            alerts.append("low_fuel")
        if hasattr(ac, "emergency_index"):
            if ac.emergency_index >= 1:
                alerts.append("low_fuel")
            if ac.emergency_index == 3:
                alerts.append("critical_emergency")

        # Calculate separation
        closest_callsign = None
        closest_dist = None
        conflict_risk = "none"

        aircraft_list = list(self.engine.aircrafts.values())
        for other_ac in aircraft_list:
            if other_ac.callsign == ac.callsign:
                continue
            dist_km = math.sqrt((ac.x - other_ac.x) ** 2 + (ac.y - other_ac.y) ** 2)
            alt_diff = abs(ac.altitude - other_ac.altitude)

            if closest_callsign is None or dist_km < closest_dist:
                closest_callsign = other_ac.callsign
                closest_dist = round(dist_km, 2)

                # Determine conflict risk
                if dist_km < 5.0 and alt_diff < 1500:
                    conflict_risk = "high"
                elif dist_km < 10.0 and alt_diff < 3000 and conflict_risk != "high":
                    conflict_risk = "medium"

        separation = Separation(
            closest_traffic=closest_callsign,
            distance=closest_dist,
            conflict_risk=conflict_risk,
        )

        severity_index = 1.0
        if ac.is_emergency:
            severity_index = round(min(2.0 ** (ac.emergency_timer / 10.0), 1000.0), 2)

        current_state_time = ac.historical_state_times.get(ac.state, 0.0)
        historical = {
            s: round(t, 1)
            for s, t in ac.historical_state_times.items()
            if s != ac.state
        }

        timing_stats = TimingStats(
            total_time_active_sec=round(ac.total_time_active, 1),
            time_in_current_state_sec=round(current_state_time, 1),
            historical_times=historical,
        )

        safety_metrics = SafetyMetrics(
            separation_warnings_triggered=ac.separation_warnings,
            closest_proximity_km=ac.closest_proximity_km
            if ac.closest_proximity_km != 999.0
            else None,
        )

        command_rejections = list(ac.command_rejections)

        return AircraftObservation(
            callsign=ac.callsign,
            position=position,
            motion=motion,
            intent=intent,
            alerts=alerts,
            separation=separation,
            timing_stats=timing_stats,
            safety_metrics=safety_metrics,
            command_rejections=command_rejections,
            severity_index=severity_index,
        )

    def _get_reward_breakdown(self) -> dict[str, float]:
        """Get per-rubric reward breakdown from the last step."""
        if hasattr(self.rubric, "_last_rewards"):
            return dict(self.rubric._last_rewards)
        return {}

    def _check_terminal_conditions(self, observation: ATCObservation) -> bool:
        """
        Check if episode should terminate.

        Args:
            observation: Current ATCObservation

        Returns:
            True if episode should end, False otherwise
        """
        # Check if simulation engine already marked terminal
        if self.engine.is_terminal:
            return True

        # Check collision (separation < 0.3km and alt diff < 300ft)
        for ac in observation.aircraft:
            for other in observation.aircraft:
                if other.callsign == ac.callsign:
                    continue
                # Calculate actual distance
                dist = self._calculate_distance(
                    ac.position.distance,
                    ac.position.segment,
                    other.position.distance,
                    other.position.segment,
                )
                alt_diff = abs(ac.position.altitude - other.position.altitude)
                if dist < 0.3 and alt_diff < 300:
                    return True

        # Check fuel exhaustion
        for ac in observation.aircraft:
            if "critical_emergency" in ac.alerts:
                return True

        # Check airspace exit (if altitude goes negative or exceeds limit)
        for ac in observation.aircraft:
            if ac.position.altitude < 0 or ac.position.altitude > 45000:
                return True

        # Check if all aircraft have landed or exited
        active_count = observation.metrics.planes_active
        if (
            active_count == 0
            and self._initial_aircraft_count > 0
            and not self._pending_spawns
        ):
            return True

        return False

    def _calculate_distance(
        self, dist1: float, seg1: str, dist2: float, seg2: str
    ) -> float:
        """
        Calculate distance between two aircraft in km.

        Args:
            dist1: Distance of first aircraft from center
            seg1: Segment of first aircraft
            dist2: Distance of second aircraft from center
            seg2: Segment of second aircraft

        Returns:
            Distance in km
        """
        x1, y1 = self._segment_to_xy(dist1, seg1)
        x2, y2 = self._segment_to_xy(dist2, seg2)
        return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

    def _segment_to_xy(self, distance: float, segment: str) -> tuple[float, float]:
        """
        Convert segment and distance to x, y coordinates.

        Args:
            distance: Distance from center in km
            segment: Segment name (e.g., "North", "North-East")

        Returns:
            Tuple of (x, y) coordinates
        """
        segment_angles = {
            "North": 0,
            "North-East": 45,
            "East": 90,
            "South-East": 135,
            "South": 180,
            "South-West": 225,
            "West": 270,
            "North-West": 315,
        }
        angle = math.radians(segment_angles.get(segment, 0))
        x = distance * math.cos(angle)
        y = distance * math.sin(angle)
        # Convert to standard coordinate system (East=+x, North=+y)
        return x, y

    def _get_terminal_event(self) -> Optional[str]:
        """
        Get the terminal event type that ended the episode.

        Returns:
            String describing terminal event or None
        """
        # Check recent events for crash/terminal indicators
        for event in reversed(self.engine.event_buffer):
            if event.get("type") == "CRASH":
                return f"CRASH: {event.get('subtype', 'UNKNOWN')}"
            elif event.get("type") == "SEPARATION_VIOLATION":
                return "SEPARATION_VIOLATION"

        if self.engine.is_terminal:
            return "ENGINE_TERMINAL"

        return "ALL_AIRCRAFT_HANDLED"

    @property
    def state(self) -> ATCState:
        """
        Return current episode metadata.

        Returns:
            ATCState Pydantic model
        """
        return ATCState(
            episode_id=self.episode_id,
            step_count=self.step_count,
            task_name=self.task_name or "unknown",
            cumulative_reward=round(self.cumulative_reward, 2),
        )


class PointDirect:
    """Minimal Point-like object for airport config."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class WaypointDirect:
    """Minimal Waypoint-like object for airport config."""

    def __init__(self, wp_data: dict):
        for key, value in wp_data.items():
            setattr(self, key, value)
        self._data = wp_data

    def model_dump(self):
        return self._data


class RunwayDirect:
    """Minimal Runway-like object for airport config."""

    def __init__(self, runway_data: dict):
        self.id = runway_data["id"]
        self.heading = runway_data.get("heading", 0)
        self.length_km = runway_data.get("length_km", 3.0)
        self.start = (
            PointDirect(**runway_data["start"])
            if "start" in runway_data
            else PointDirect(0, 0)
        )
        self.end = (
            PointDirect(**runway_data["end"])
            if "end" in runway_data
            else PointDirect(0, 0)
        )
        self.iaf = PointDirect(**runway_data["iaf"]) if "iaf" in runway_data else None
        self.altitude = runway_data.get("altitude", 0)
        self.dp = runway_data.get("dp")
        self.model_dump = lambda: runway_data


class AirportConfigDirect:
    """
    Minimal AirportConfig-like object for direct JSON loading.

    Provides the interface expected by engine.load_airport() without
    requiring the full pydantic models from api.schemas.
    """

    def __init__(self, data: dict):
        self._data = data
        self.airport_code = data["airport_code"]
        self.name = data.get("name", data["airport_code"])
        self.gates = {
            name: PointDirect(**pos) for name, pos in data.get("gates", {}).items()
        }
        self.terminal_gates = {
            name: PointDirect(**pos)
            for name, pos in data.get("terminal_gates", {}).items()
        }
        self.runways = [RunwayDirect(r) for r in data.get("runways", [])]
        self.waypoints = {
            k: WaypointDirect(v) for k, v in data.get("waypoints", {}).items()
        }
        self.stars = data.get("stars", {})
        self.sids = data.get("sids", {})
        self.time_scale = data.get("time_scale", 1.0)

    def model_dump(self):
        return self._data


# Import time at module level for use in methods
import time
