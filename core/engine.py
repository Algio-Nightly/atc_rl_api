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
        
        self.event_buffer = []

    def load_airport(self, config):
        """Load a new airport configuration and reset the simulation"""
        self.reset_environment()
        self.config = config
        
        # Determine initial active runways based on default wind
        self.update_weather(self.wind_heading, self.wind_speed)
        
        self.event_buffer.append({
            "type": "AIRPORT_LOADED", 
            "code": self.config.airport_code, 
            "timestamp": time.time(),
            "msg": f"Airport {config.name} loaded. Active RWYs: {', '.join(self.active_runways)}"
        })

    def update_config(self, config):
        """Update the configuration without resetting the simulation state"""
        self.config = config
        # Re-evaluate weather logic to ensure active runways are still valid
        self.update_weather(self.wind_heading, self.wind_speed)
        
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
                        
                        # Add runway's internal IAF
                        rw_cfg = next((r for r in self.config.runways if r.id == active_rw_id), None)
                        if rw_cfg:
                            iaf_wp = {"x": rw_cfg.iaf.x, "y": rw_cfg.iaf.y, "target_alt": 3000, "target_speed": 180, "name": f"IAF-{active_rw_id}"}
                            route.append(iaf_wp)
                        
                        gate_routes.append({"runway": active_rw_id, "waypoints": route})
                if gate_routes:
                    stars[gate_id] = gate_routes

        context = {
            "wind_heading": self.wind_heading,
            "wind_speed": self.wind_speed,
            "stars": stars
        }
        
        to_delete = []
        for callsign, aircraft in list(self.aircrafts.items()):
            aircraft.update(dt, context)
            
            # Use (0,0) as center for landing detection
            cx = 0
            cy = 0
            dist_to_airport = math.sqrt((aircraft.x - cx)**2 + (aircraft.y - cy)**2)
            
            if aircraft.state == "APPROACH" and dist_to_airport < 1.0:
                self.event_buffer.append({"type": "LANDING", "callsign": callsign, "reward": 100, "timestamp": time.time()})
                to_delete.append(callsign)
            
            if aircraft.state == "CRASHED":
                self.is_terminal = True
                self.event_buffer.append({"type": "CRASH", "callsign": callsign, "reward": -500, "timestamp": time.time()})

        for callsign in to_delete:
            if callsign in self.aircrafts:
                del self.aircrafts[callsign]

        self.check_separation_violations()

    def check_separation_violations(self):
        callsigns = list(self.aircrafts.keys())
        for i in range(len(callsigns)):
            for j in range(i + 1, len(callsigns)):
                a1 = self.aircrafts[callsigns[i]]
                a2 = self.aircrafts[callsigns[j]]
                dist = math.sqrt((a1.x - a2.x)**2 + (a1.y - a2.y)**2)
                alt_diff = abs(a1.altitude - a2.altitude)
                # Hardcoded separation mins for now (5km/1000ft)
                if dist < 0.5 and alt_diff < 500:
                    self.is_terminal = True
                    self.event_buffer.append({"type": "COLLISION", "participants": [a1.callsign, a2.callsign], "reward": -1000, "timestamp": time.time()})
                elif dist < 5.0 and alt_diff < 1000:
                    self.event_buffer.append({"type": "SEPARATION_VIOLATION", "participants": [a1.callsign, a2.callsign], "reward": -50, "timestamp": time.time()})

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

        new_ac = Aircraft(callsign.upper(), ac_type, weight_class, pos, altitude, heading, speed, active_star=gate)
        self.aircrafts[callsign.upper()] = new_ac
        self.event_buffer.append({
            "type": "SPAWN", 
            "callsign": callsign.upper(), 
            "ac_type": ac_type, 
            "weight_class": weight_class,
            "timestamp": time.time()
        })
        return True

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
        
        state = {
            "simulation_time": round(self.simulation_time, 2),
            "is_terminal": self.is_terminal,
            "active_runways": self.active_runways,
            "wind_heading": self.wind_heading,
            "wind_speed": self.wind_speed,
            "time_scale": self.time_scale,
            "aircrafts": {c: a.get_state(anchor=anchor) for c, a in self.aircrafts.items()},
            "events": list(self.event_buffer),
            "config": config_data
        }
        self.event_buffer = []
        return state
