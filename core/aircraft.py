 # Aircraft class for physics kinematics

import math

class Aircraft:
    def __init__(self, 
                 callsign: str, 
                 type: str,
                 weight_class: str,
                 position: tuple[float, float], 
                 altitude: float, 
                 heading: float, 
                 speed: float,
                 state: str = "ENROUTE",
                 fuel_level: float = 100.0,
                 emergency_index: int = 0,
                 active_star: str = None):
        self.callsign = callsign
        self.type = type
        self.weight_class = weight_class
        self.x, self.y = position
        
        self.altitude = altitude  # Current Feet
        self.target_alt = altitude
        
        self.heading = heading    # Current Degrees
        self.target_heading = heading
        
        self.speed = speed        # Current Knots
        self.target_speed = speed
        
        self.state = state
        self.fuel_level = fuel_level
        self.emergency_index = emergency_index
        
        # STAR navigation
        self.active_star = active_star
        self.wp_index = 0
        self.direct_to_wp = None # WaypointConfig if active
        
        # Holding logic
        self.holding_fix = None # {"x", "y"}
        self.holding_radius = 2.0 # km
        
        # Physics constraints
        self.turn_rate = 3.0       # Degrees per second
        self.accel_rate = 2.0      # Knots per second
        self.alt_rate = 25.0       # Feet per second (~1500 fpm)
        self.fuel_burn_rate = 0.01 # Fuel % per second

    def update(self, dt: float, engine_context: dict = None):
        """Update physics kinematics for the given time step dt"""
        
        # 0. Navigation Logic (STAR or HOLDING)
        if engine_context:
            wind_h = engine_context.get("wind_heading", 0)
            wind_s = engine_context.get("wind_speed", 0)
            stars = engine_context.get("stars", {})

            if self.state == "HOLDING" and self.holding_fix:
                # 0a. Holding Pattern (Orbital)
                fx, fy = self.holding_fix["x"], self.holding_fix["y"]
                dx = fx - self.x
                dy = fy - self.y
                dist_to_fix = math.sqrt(dx**2 + dy**2)
                angle_to_fix = math.degrees(math.atan2(dy, dx))
                
                # Orbit logic: Steer 90 deg from fix, with correction to maintain radius
                # Clockwise orbit
                offset = 90
                correction = (dist_to_fix - self.holding_radius) * 20 # Sharp correction
                correction = max(-70, min(70, correction))
                
                target_math = (angle_to_fix + offset + correction)
                self.target_heading = (90 - target_math) % 360

            elif self.direct_to_wp:
                # 0b. Direct-To Logic
                dx = self.direct_to_wp["x"] - self.x
                dy = self.direct_to_wp["y"] - self.y
                self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                self.target_alt = self.direct_to_wp["target_alt"]
                self.target_speed = self.direct_to_wp["target_speed"]

                if math.sqrt(dx**2 + dy**2) < 1.0:
                    self.direct_to_wp = None # Reached, continue from current wp_index or hold
                    # If we have a star, continue from wherever we are
                    # (Usually direct_to is used to jump ahead in a star)

            elif self.state == "APPROACH":
                # 0c. Approach Logic (Final Alignment)
                # Head towards airport center but strictly align with runway first
                # For now, just maintain heading to center
                pass

            elif self.active_star and self.active_star in stars:
                # 0d. STAR Navigation Logic (Multi-Runway Aware)
                routes = stars[self.active_star]
                if not routes:
                    self.active_star = None
                    return

                # Pick a route (usually the first one if we don't have a runway assignment)
                # TODO: Support explicit runway assignments
                selected_route = routes[0]["waypoints"]
                
                if self.wp_index < len(selected_route):
                    wp = selected_route[self.wp_index]
                    self.target_alt = wp["target_alt"]
                    self.target_speed = wp["target_speed"]
                    
                    dx = wp["x"] - self.x
                    dy = wp["y"] - self.y
                    self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                    
                    if math.sqrt(dx**2 + dy**2) < 2.0:
                        self.wp_index += 1
                        if self.wp_index >= len(selected_route):
                            self.active_star = None
                            self.wp_index = 0
                            self.state = "APPROACH"
        
        # 1. Update Heading towards Target
        heading_diff = (self.target_heading - self.heading + 180) % 360 - 180
        if abs(heading_diff) > 0.1:
            turn_step = math.copysign(min(abs(heading_diff), self.turn_rate * dt), heading_diff)
            self.heading = (self.heading + turn_step) % 360

        # ... (speed/alt/fuel same)
        # 2. Update Speed towards Target
        speed_diff = self.target_speed - self.speed
        if abs(speed_diff) > 0.1:
            accel_step = math.copysign(min(abs(speed_diff), self.accel_rate * dt), speed_diff)
            self.speed += accel_step

        # 3. Update Altitude towards Target
        alt_diff = self.target_alt - self.altitude
        if abs(alt_diff) > 1.0:
            alt_step = math.copysign(min(abs(alt_diff), self.alt_rate * dt), alt_diff)
            self.altitude += alt_step

        # 4. Fuel Consumption
        self.fuel_level = max(0.0, self.fuel_level - self.fuel_burn_rate * dt)
        if self.fuel_level < 10.0 and self.emergency_index < 1:
            self.emergency_index = 1 # Low fuel warning
        elif self.fuel_level <= 0:
            self.state = "CRASHED"
            self.speed = 0

        # 5. Movement math (Wind aware)
        if self.state != "CRASHED":
            # Air velocity vector (based on heading and airspeed)
            rad_heading = math.radians(90 - self.heading)
            v_air_x = self.speed * math.cos(rad_heading)
            v_air_y = self.speed * math.sin(rad_heading)
            
            # Wind velocity vector (wind_heading is FROM)
            wind_h = engine_context.get("wind_heading", 0) if engine_context else 0
            wind_s = engine_context.get("wind_speed", 0) if engine_context else 0
            rad_wind_to = math.radians(90 - (wind_h + 180) % 360)
            v_wind_x = wind_s * math.cos(rad_wind_to)
            v_wind_y = wind_s * math.sin(rad_wind_to)
            
            # Ground velocity = Air velocity + Wind velocity
            vx_ground = v_air_x + v_wind_x
            vy_ground = v_air_y + v_wind_y
            
            self.x += (vx_ground * 1.852 / 3600) * dt
            self.y += (vy_ground * 1.852 / 3600) * dt

    def get_state(self, anchor=None):
        """Returns state, projecting to lat/lon if anchor is provided"""
        res = {
            "callsign": self.callsign,
            "type": self.type,
            "weight_class": self.weight_class,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "altitude": int(self.altitude),
            "target_alt": int(self.target_alt),
            "heading": round(self.heading, 1),
            "target_heading": round(self.target_heading, 1),
            "speed": int(self.speed),
            "target_speed": int(self.target_speed),
            "state": self.state,
            "fuel_level": round(self.fuel_level, 1),
            "emergency_index": self.emergency_index,
            "active_star": self.active_star,
            "wp_index": self.wp_index,
            "is_holding": self.state == "HOLDING"
        }
        
        if anchor:
            # Planar projection logic: 111.32 km per degree lat
            # Anchor is now at (0,0) center
            KM_PER_DEG_LAT = 111.32
            dx = self.x
            dy = self.y
            
            # Use same math as config_handler for consistency
            res["lat"] = round(anchor["lat"] + (dy / KM_PER_DEG_LAT), 6)
            res["lon"] = round(anchor["lon"] + (dx / (KM_PER_DEG_LAT * math.cos(math.radians(anchor["lat"])))), 6)
            
        return res
