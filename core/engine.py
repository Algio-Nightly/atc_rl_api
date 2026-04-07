import time
import asyncio
import math
from .aircraft import Aircraft

class SimulationEngine:
    def __init__(self, time_step: float = 0.1):
        self.aircrafts: dict[str, Aircraft] = {}
        self.simulation_time = 0.0
        self.is_active = False
        self.is_terminal = False
        self.time_scale = 1.0
        self.tick_rate = time_step
        
        # Current loaded configuration
        self.config = None # Will be of type AirportConfig
        
        # Weather State
        self.wind_heading = 90.0
        self.wind_speed = 10.0
        self.active_runways: list[str] = []
        self.runway_status: dict[str, dict] = {} # {id: {occupied_by: Optional[str]}}
        self.runway_cooldowns: dict[str, float] = {} # {id: timestamp_until_free}
        
        self.event_buffer = []

    def load_airport(self, config):
        """Load a new airport configuration and reset the simulation"""
        self.reset_environment()
        self.config = config
        self.time_scale = config.time_scale if hasattr(config, 'time_scale') else 1.0
        
        # Determine initial active runways based on default wind
        self.update_weather(self.wind_heading, self.wind_speed)
        
        # Initialize runway status
        self.runway_status = {r.id: {"occupied_by": None} for r in self.config.runways}
        self.runway_cooldowns = {r.id: 0.0 for r in self.config.runways}
        
        self.event_buffer.append({
            "type": "AIRPORT_LOADED", 
            "code": self.config.airport_code, 
            "timestamp": time.time(),
            "msg": f"Airport {config.name} loaded. Active RWYs: {', '.join(self.active_runways)}"
        })

    def update_config(self, config):
        """Update the configuration without resetting the simulation state"""
        self.config = config
        if hasattr(config, 'time_scale'):
            self.time_scale = config.time_scale
            
        # Re-evaluate weather logic to ensure active runways are still valid
        self.update_weather(self.wind_heading, self.wind_speed)

        # Sync runway status
        for r in self.config.runways:
            if r.id not in self.runway_status:
                self.runway_status[r.id] = {"occupied_by": None}
        
        self.event_buffer.append({
            "type": "INFO", 
            "msg": f"Config updated. Active RWYs: {', '.join(self.active_runways)}", 
            "timestamp": time.time()
        })

    async def run(self, on_step=None):
        self.is_active = True
        print("[Sim Engine] Simulation loop started.")
        last_time = time.perf_counter()
        tick_count = 0
        while self.is_active:
            try:
                current_time = time.perf_counter()
                actual_dt = current_time - last_time
                last_time = current_time
                dt = actual_dt * self.time_scale
                
                # Step only if NOT terminal
                if not self.is_terminal and self.config:
                    self.step(dt)
                    
                # ALWAYS broadcast if on_step is provided, even if terminal
                if on_step:
                    await on_step(self.get_full_state())
                
                tick_count += 1
                if tick_count % 100 == 0:
                    print(f"[Sim Engine] Heartbeat @ t={self.simulation_time:.1f}s, Scale={self.time_scale}x")

                execution_time = time.perf_counter() - current_time
                sleep_time = max(0.01, self.tick_rate - execution_time)
                await asyncio.sleep(sleep_time)
            except Exception as e:
                print(f"[Sim Engine Critical Error] {e}")
                await asyncio.sleep(0.5) # Throttle on error

    def step(self, dt: float):
        self.simulation_time += dt
        
        # Build STAR context from config
        stars = {}
        if self.config and self.active_runways:
            # Resolve stars for ALL active runways
            for gate_id, runway_star_map in self.config.stars.items():
                gate_routes = []
                for active_rw_id in self.active_runways:
                    if active_rw_id in runway_star_map:
                        wp_ids = runway_star_map[active_rw_id]
                        route = []
                        for wp_id in wp_ids:
                            wp_cfg = self.config.waypoints.get(wp_id)
                            if wp_cfg:
                                route.append(wp_cfg.model_dump())
                        
                        gate_routes.append({"runway": active_rw_id, "waypoints": route})
                if gate_routes:
                    stars[gate_id] = gate_routes
        
        context = {
            "wind_heading": self.wind_heading,
            "wind_speed": self.wind_speed,
            "stars": stars,
            "runway_status": self.runway_status,
        }
        
        to_delete = []
        for callsign, aircraft in list(self.aircrafts.items()):
            aircraft.update(dt, context)
            
            # Use assigned runway's threshold for landing detection
            # SUCCESSFUL LANDING Detection
            if aircraft.state == "LANDING" and aircraft.speed < 10:
                self.event_buffer.append({"type": "SUCCESSFUL_LANDING", "callsign": callsign, "timestamp": time.time()})
                if aircraft.target_runway_id in self.runway_status:
                    self.runway_status[aircraft.target_runway_id]["occupied_by"] = None
                    self.runway_cooldowns[aircraft.target_runway_id] = self.simulation_time + 60.0
                to_delete.append(callsign)
            
            # SUCCESSFUL DEPARTURE Detection (45km Boundary)
            if aircraft.state == "CLIMB_OUT":
                dist_from_center = math.sqrt(aircraft.x**2 + aircraft.y**2)
                if dist_from_center > 45.0:
                    self.event_buffer.append({
                        "type": "SUCCESSFUL_DEPARTURE", 
                        "callsign": callsign, 
                        "reward": 100, 
                        "timestamp": time.time()
                    })
                    to_delete.append(callsign)
            
            if aircraft.state == "CRASHED" or aircraft.state == "CRASHED_RUNWAY_INCURSION":
                self.trigger_crash(callsign, aircraft.state)
                # Release lock if they crash while on runway
                if aircraft.target_runway_id in self.runway_status:
                    if self.runway_status[aircraft.target_runway_id]["occupied_by"] == callsign:
                        self.runway_status[aircraft.target_runway_id]["occupied_by"] = None

            # 1. CFIT Detection (Controlled Flight Into Terrain)
            # Below 50ft when not in a ground/landing state
            if aircraft.altitude < 50 and aircraft.state not in ["ON_GATE", "TAXIING", "HOLDING_SHORT", "LINE_UP", "TAKEOFF_ROLL", "LANDING", "APPROACH", "CLIMB_OUT"]:
                self.trigger_crash(callsign, "CFIT")

            # 2. Runway Overshoot (Overrun) Detection
            # If in LANDING state and past the runway boundary at high speed
            if aircraft.state == "LANDING" and aircraft.target_runway_id:
                rw_cfg = next((r for r in self.config.runways if r.id == aircraft.target_runway_id), None)
                if rw_cfg:
                    # Check distance from threshold vs runway length
                    dist_from_threshold = math.sqrt((aircraft.x - rw_cfg.start.x)**2 + (aircraft.y - rw_cfg.start.y)**2)
                    if dist_from_threshold > (rw_cfg.length_km + 0.1) and aircraft.speed > 20:
                        self.trigger_crash(callsign, "OVERRUN")

        for callsign in to_delete:
            if callsign in self.aircrafts:
                del self.aircrafts[callsign]

        self.check_separation_violations()

    def trigger_crash(self, callsign: str, subtype: str, participants: list[str] = None):
        """Centralized crash handler"""
        if self.is_terminal: return
        self.is_terminal = True
        self.event_buffer.append({
            "type": "CRASH", 
            "subtype": subtype,
            "callsign": callsign, 
            "participants": participants or [callsign],
            "timestamp": time.time(),
            "msg": f"CRASH: {subtype} involving {', '.join(participants or [callsign])}"
        })

    def check_separation_violations(self):
        callsigns = list(self.aircrafts.keys())
        for i in range(len(callsigns)):
            for j in range(i + 1, len(callsigns)):
                a1 = self.aircrafts[callsigns[i]]
                a2 = self.aircrafts[callsigns[j]]
                dist = math.sqrt((a1.x - a2.x)**2 + (a1.y - a2.y)**2)
                alt_diff = abs(a1.altitude - a2.altitude)
                
                # COLLISION (MAC): < 0.3km (300m) AND < 300ft
                if dist < 0.3 and alt_diff < 300:
                    self.trigger_crash(a1.callsign, "MAC", [a1.callsign, a2.callsign])
                
                # SEPARATION VIOLATION: < 5km AND < 1000ft
                elif dist < 5.0 and alt_diff < 1000:
                    # Skip violation if they are on ground close to each other
                    if a1.altitude < 100 and a2.altitude < 100:
                        continue
                    self.event_buffer.append({"type": "SEPARATION_VIOLATION", "participants": [a1.callsign, a2.callsign], "timestamp": time.time()})

    def reset_environment(self):
        self.aircrafts = {}
        self.simulation_time = 0.0
        self.is_terminal = False
        self.event_buffer = []

    def remove_aircraft(self, callsign: str):
        if callsign in self.aircrafts:
            del self.aircrafts[callsign]
            self.event_buffer.append({"type": "AIRCRAFT_REMOVED", "callsign": callsign, "timestamp": time.time()})
            return True
        return False

    def add_aircraft(self, callsign, ac_type, weight_class, gate, altitude=10000, heading=None, speed=250):
        if not self.config or gate not in self.config.gates:
            return False
            
        gate_pos = self.config.gates[gate]
        pos = (gate_pos.x, gate_pos.y)
        
        # Default heading: points toward center (0,0)
        if heading is None:
            dx = 0 - pos[0]
            dy = 0 - pos[1]
            heading = (90 - math.degrees(math.atan2(dy, dx))) % 360

        new_ac = Aircraft(callsign.upper(), ac_type, weight_class, pos, altitude, heading, speed, active_star=gate, gate=gate)
        self.aircrafts[callsign.upper()] = new_ac
        self.event_buffer.append({
            "type": "SPAWN", 
            "callsign": callsign.upper(), 
            "ac_type": ac_type, 
            "weight_class": weight_class,
            "timestamp": time.time()
        })
        return True

    def spawn_departure(self, callsign: str, ac_type: str, runway_id: str, gate_id: str, terminal_gate_id: str = None):
        """Spawns an aircraft on the ground for a SID departure."""
        if not self.config: return None
        
        # Find runway config
        rw_cfg = next((r for r in self.config.runways if r.id == runway_id), None)
        if not rw_cfg: return None
        
        # Determine spawn point and state
        start_p = rw_cfg.start
        initial_state = "HOLDING_SHORT"
        
        if terminal_gate_id and terminal_gate_id in self.config.terminal_gates:
            gate_p = self.config.terminal_gates[terminal_gate_id]
            start_p = gate_p
            initial_state = "ON_GATE"
            
        # Build SID route: Runway -> DP -> Gate
        sid_wp_ids = self.config.sids.get(runway_id, {}).get(gate_id, [])
        route = []
        for wp_id in sid_wp_ids:
            wp = self.config.waypoints.get(wp_id)
            if wp: 
                route.append(wp.model_dump())
            elif wp_id in self.config.gates:
                # Boundary gate is a "virtual waypoint"
                gate_p = self.config.gates[wp_id]
                route.append({
                    "id": wp_id,
                    "name": wp_id,
                    "x": gate_p.x,
                    "y": gate_p.y,
                    "target_alt": 6000,
                    "target_speed": 250
                })
        
        # Create Aircraft
        ac = Aircraft(
            callsign=callsign.upper(),
            type=ac_type,
            weight_class="Heavy" if any(x in ac_type for x in ["74", "77", "78", "380"]) else "Medium",
            position=(start_p.x, start_p.y),
            altitude=0,
            heading=rw_cfg.heading,
            speed=0,
            state=initial_state,
            gate=gate_id
        )
        
        # Initialize departure state
        ac.target_runway_id = runway_id
        ac.runway_threshold = {"x": rw_cfg.start.x, "y": rw_cfg.start.y}
        ac.runway_heading = rw_cfg.heading
        ac.active_route = route
        ac.route_index = 0
        
        self.aircrafts[callsign.upper()] = ac
        
        self.event_buffer.append({
            "type": "SPAWN", 
            "subtype": "DEPARTURE",
            "callsign": callsign.upper(), 
            "runway": runway_id, 
            "timestamp": time.time()
        })
        return ac

    def update_weather(self, heading: float, speed: float):
        self.wind_heading = heading
        self.wind_speed = speed
        
        if not self.config or not self.config.runways:
            self.active_runways = []
            return

        old_runways = list(self.active_runways)
        
        # 1. Selection logic: Select all runways with ANY headwind component (< 90 deg diff)
        # diff = (r.heading - wind_heading + 180) % 360 - 180
        # abs(diff) < 90 means it has a headwind component.
        new_active = []
        for r in self.config.runways:
            diff = (r.heading - heading + 180) % 360 - 180
            if abs(diff) < 90:
                new_active.append(r.id)
        
        # 2. Safety Fallback: If no runway has a headwind component, pick the single best one (least tailwind)
        if not new_active and self.config.runways:
            best_rw = min(self.config.runways, key=lambda r: abs((r.heading - heading + 180) % 360 - 180))
            new_active = [best_rw.id]
            
        self.active_runways = new_active
        
        if set(self.active_runways) != set(old_runways):
            self.event_buffer.append({
                "type": "RUNWAY_CHANGE", 
                "from": old_runways,
                "to": self.active_runways,
                "timestamp": time.time()
            })
            # Transition existing enroute aircraft to HOLDING so they can be re-cleared for new active runways
            for ac in self.aircrafts.values():
                if ac.active_star:
                    ac.active_star = None
                    ac.state = "HOLDING"

    def get_full_state(self):
        config_data = self.config.model_dump() if self.config else None
        anchor = config_data["anchor"] if config_data else None
        
        # Calculate dynamic runway status for the UI
        # 1. Start with base occupied_by from engine locks
        display_runway_status = {}
        for r_id, status in self.runway_status.items():
            effective_status = {
                "id": r_id,
                "status": "CLEAR",
                "occupied_by": status["occupied_by"],
                "reserved_by": None,
                "cooldown_remaining": max(0, round(self.runway_cooldowns.get(r_id, 0) - self.simulation_time, 1))
            }
            
            # Priority 1: Physical Occupancy (Lock)
            if status["occupied_by"]:
                effective_status["status"] = "OCCUPIED"
            # Priority 2: Cooldown
            elif effective_status["cooldown_remaining"] > 0:
                effective_status["status"] = "COOLDOWN"
            # Priority 3: Reservations (Assignments)
            else:
                # Check for any aircraft that is actively using or approaching this runway
                for ac in self.aircrafts.values():
                    # 1. Skip if still at terminal (don't block runway yet)
                    if ac.state == "ON_GATE":
                        continue
                        
                    is_reserving = False
                    # 2. Check if this is their target runway and they are in an active phase
                    if ac.target_runway_id == r_id:
                        # Arrivals in ENROUTE/HOLDING don't reserve yet
                        # Departures in TAXIING/HOLDING_SHORT do reserve
                        if ac.state in ["TAXIING", "HOLDING_SHORT", "APPROACH", "LANDING", "GO_AROUND"]:
                            is_reserving = True
                            
                    # 3. Check for queued landings (explicitly cleared)
                    if not is_reserving and ac.queued_landing and ac.queued_landing.get("runway_id") == r_id:
                        is_reserving = True
                        
                    if is_reserving:
                        effective_status["status"] = "RESERVED"
                        effective_status["reserved_by"] = ac.callsign
                        break
            
            display_runway_status[r_id] = effective_status

        state = {
            "simulation_time": round(self.simulation_time, 2),
            "is_terminal": self.is_terminal,
            "active_runways": self.active_runways,
            "wind_heading": self.wind_heading,
            "wind_speed": self.wind_speed,
            "time_scale": self.time_scale,
            "aircrafts": {c: a.get_state(anchor=anchor) for c, a in self.aircrafts.items()},
            "runway_status": display_runway_status,
            "events": list(self.event_buffer),
            "config": config_data
        }
        self.event_buffer = []
        return state
