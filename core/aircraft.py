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
        
        # Holding logic
        self.holding_fix = None # (x, y)
        self.holding_radius = 3.0 # km
        
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
                fx, fy = self.holding_fix
                dx = fx - self.x
                dy = fy - self.y
                dist_to_fix = math.sqrt(dx**2 + dy**2)
                
                # Angle from aircraft to fix
                angle_to_fix = math.degrees(math.atan2(dy, dx))
                
                # We want to maintain holding_radius. 
                # If too far: steer more towards fix.
                # If too close: steer more away.
                # Base orbit: +90 degrees from angle_to_fix for clockwise
                offset = 90
                # Corrective factor: steering inwards if too far
                correction = (dist_to_fix - self.holding_radius) * 15 # 15 deg adjustment per km
                correction = max(-60, min(60, correction))
                
                orbit_heading_math = (angle_to_fix + offset + correction)
                self.target_heading = (90 - orbit_heading_math) % 360

            elif self.active_star and self.active_star in stars:
                # 0b. STAR Navigation Logic
                waypoints = stars[self.active_star]
                if self.wp_index < len(waypoints):
                    wp = waypoints[self.wp_index]
                    self.target_alt = wp["target_alt"]
                    self.target_speed = wp["target_speed"]
                    
                    dx = wp["x"] - self.x
                    dy = wp["y"] - self.y
                    self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                    
                    if math.sqrt(dx**2 + dy**2) < 2.0:
                        self.wp_index += 1
                        if self.wp_index >= len(waypoints):
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

    def get_state(self):
        return {
            "callsign": self.callsign,
            "type": self.type,
            "weight_class": self.weight_class,
            "x": self.x,
            "y": self.y,
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
