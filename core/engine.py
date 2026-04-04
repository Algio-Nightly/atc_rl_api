import time
import asyncio
import math
from .aircraft import Aircraft
from .constants import RUNWAY_HEADINGS, ARRIVAL_GATES, HOLDING_FIXES, MIN_SEPARATION_DISTANCE, MIN_VERTICAL_SEPARATION
from .routes import STAR_MATRIX

class SimulationEngine:
    def __init__(self, time_step: float = 0.1):
        self.aircrafts: dict[str, Aircraft] = {}
        self.simulation_time = 0.0
        self.is_active = False
        self.is_terminal = False
        self.time_scale = 1.0  # Speed multiplier
        self.tick_rate = time_step # Target real-world delay between ticks (e.g. 0.1s for 10Hz)
        
        # Weather State
        self.wind_heading = 90.0
        self.wind_speed = 10.0
        self.active_runway = "09"
        
        # Event tracking (for rewards/penalties)
        self.event_buffer = []

    async def run(self, on_step=None):
        """Main background simulation loop"""
        self.is_active = True
        last_time = time.perf_counter()
        
        while self.is_active:
            current_time = time.perf_counter()
            actual_dt = current_time - last_time
            last_time = current_time
            
            # Apply time acceleration to the physics step
            dt = actual_dt * self.time_scale
            
            if not self.is_terminal:
                self.step(dt)
                
            # Real-time state broadcasting/reporting hook
            if on_step and not self.is_terminal:
                state = self.get_full_state()
                await on_step(state)
            
            # Sleep to maintain tick rate (adjusting for execution time)
            execution_time = time.perf_counter() - current_time
            sleep_time = max(0, self.tick_rate - execution_time)
            await asyncio.sleep(sleep_time)

    def step(self, dt: float):
        """Execute one physics step with delta time dt"""
        self.simulation_time += dt
        
        # Context to pass to aircraft (wind, active stars)
        context = {
            "wind_heading": self.wind_heading,
            "wind_speed": self.wind_speed,
            "stars": STAR_MATRIX.get(self.active_runway, {})
        }
        
        to_delete = []
        for callsign, aircraft in list(self.aircrafts.items()):
            aircraft.update(dt, context)
            
            # Check for landing (simple threshold logic: center of map is airport)
            dist_to_center = math.sqrt(aircraft.x**2 + aircraft.y**2)
            # Center of Gatwick is (50, 50) as per constants.py RUNWAY_POS
            dist_to_airport = math.sqrt((aircraft.x - 50)**2 + (aircraft.y - 50)**2)
            
            if aircraft.state == "APPROACH" and dist_to_airport < 2.0:
                self.event_buffer.append({"type": "LANDING", "callsign": callsign, "reward": 100})
                to_delete.append(callsign)
            
            # Check for crashed (fuel etc handled in aircraft.update)
            if aircraft.state == "CRASHED":
                self.is_terminal = True
                self.event_buffer.append({"type": "CRASH", "callsign": callsign, "reason": "Fuel/Other", "reward": -500})

        # Cleanup landed aircraft
        for callsign in to_delete:
            if callsign in self.aircrafts:
                del self.aircrafts[callsign]

        # Safety monitoring
        self.check_separation_violations()

    def check_separation_violations(self):
        """Check for separation losses or collisions"""
        callsigns = list(self.aircrafts.keys())
        for i in range(len(callsigns)):
            for j in range(i + 1, len(callsigns)):
                a1 = self.aircrafts[callsigns[i]]
                a2 = self.aircrafts[callsigns[j]]
                
                dist = math.sqrt((a1.x - a2.x)**2 + (a1.y - a2.y)**2)
                alt_diff = abs(a1.altitude - a2.altitude)
                
                if dist < 0.5 and alt_diff < 500: # COLLISION
                    self.is_terminal = True
                    self.event_buffer.append({"type": "COLLISION", "participants": [a1.callsign, a2.callsign], "reward": -1000})
                elif dist < MIN_SEPARATION_DISTANCE and alt_diff < MIN_VERTICAL_SEPARATION: # LOSS OF SEPARATION
                    self.event_buffer.append({"type": "SEPARATION_VIOLATION", "participants": [a1.callsign, a2.callsign], "reward": -50})

    def reset_environment(self):
        """Wipe simulation state to defaults"""
        self.aircrafts = {}
        self.simulation_time = 0.0
        self.is_terminal = False
        self.event_buffer = []
        self.active_runway = "09"
        self.wind_heading = 90.0
        self.wind_speed = 10.0

    def add_aircraft(self, callsign, ac_type, weight_class, gate, altitude=10000, heading=180, speed=250):
        """Spawn aircraft and automatically lock onto the correct STAR"""
        if gate not in ARRIVAL_GATES:
            return False
            
        pos = ARRIVAL_GATES[gate]
        
        # Auto-Star Assignment based on Gate and Active Runway
        active_star = None
        if self.active_runway in STAR_MATRIX and gate in STAR_MATRIX[self.active_runway]:
            active_star = gate # Our matrices are keyed by gate name

        new_ac = Aircraft(callsign, ac_type, weight_class, pos, altitude, heading, speed, active_star=active_star)
        self.aircrafts[callsign] = new_ac
        self.event_buffer.append({"type": "SPAWN", "callsign": callsign})
        return True

    def update_weather(self, heading: float, speed: float):
        """Update wind and re-evaluate active runway"""
        old_runway = self.active_runway
        self.wind_heading = heading
        self.wind_speed = speed
        
        # Logic: Select runway head closest to wind direction
        # Runway headings are 90 and 270
        diff_09 = abs((heading - RUNWAY_HEADINGS["09"] + 180) % 360 - 180)
        diff_27 = abs((heading - RUNWAY_HEADINGS["27"] + 180) % 360 - 180)
        
        self.active_runway = "09" if diff_09 < diff_27 else "27"
        
        if self.active_runway != old_runway:
            self.event_buffer.append({"type": "RUNWAY_CHANGE", "from": old_runway, "to": self.active_runway})
            # Break off all STARs
            for ac in self.aircrafts.values():
                if ac.active_star:
                    ac.active_star = None
                    ac.state = "HOLDING"
                    # main.py handles assigning the holding fix once they enter HOLDING

    def get_full_state(self):
        state = {
            "simulation_time": round(self.simulation_time, 2),
            "is_terminal": self.is_terminal,
            "active_runway": self.active_runway,
            "wind_heading": self.wind_heading,
            "wind_speed": self.wind_speed,
            "time_scale": self.time_scale,
            "aircrafts": {c: a.get_state() for c, a in self.aircrafts.items()},
            "events": list(self.event_buffer)
        }
        self.event_buffer = [] # Clear buffer after reporting
        return state
