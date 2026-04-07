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
        
        # Landing & Go-Around logic
        self.target_runway_id = None
        self.runway_threshold = None # {"x", "y"}
        self.runway_heading = 0.0
        self.landing_start_dist = 0.0
        
        # Physics constraints
        self.turn_rate = 3.0       # Degrees per second
        self.accel_rate = 2.0      # Knots per second
        self.alt_rate = 25.0       # Feet per second (~1500 fpm)
        self.fuel_burn_rate = 0.01 # Fuel % per second

        # Holding Pattern State
        self.holding_fix = None
        self.holding_radius = 5.0
        
        # Queued Landing State (Delayed Landing)
        self.queued_landing = None # {runway_id, threshold, heading}

    def update(self, dt: float, engine_context: dict = None):
        """Update physics kinematics for the given time step dt"""
        
        # 0. Navigation Logic (STAR or HOLDING)
        if engine_context:
            wind_h = engine_context.get("wind_heading", 0)
            wind_s = engine_context.get("wind_speed", 0)
            stars = engine_context.get("stars", {})

            if self.state == "HOLDING" and self.holding_fix:
                # 0a. Holding Pattern (Two-Phase: Transit then Orbit)
                fx, fy = self.holding_fix["x"], self.holding_fix["y"]
                dx = fx - self.x
                dy = fy - self.y
                dist_to_fix = math.sqrt(dx**2 + dy**2)
                angle_to_fix = math.degrees(math.atan2(dy, dx))
                
                # If further than radius + buffer, fly directly to the fix
                if dist_to_fix > (self.holding_radius + 0.5):
                    # Phase 1: Transit (Direct flight to waypoint)
                    self.target_heading = (90 - angle_to_fix) % 360
                else:
                    # Phase 2: Orbit (Circular circling)
                    # Orbit logic: Steer 90 deg from fix, with correction to maintain radius
                    offset = 90 # Clockwise
                    correction = (dist_to_fix - self.holding_radius) * 20 # Sharp radial correction
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

            elif self.state == "APPROACH" and self.runway_threshold:
                # 0c. Approach Logic (Phase 1: Glide Slope LERP)
                tx, ty = self.runway_threshold["x"], self.runway_threshold["y"]
                dx = tx - self.x
                dy = ty - self.y
                dist = math.sqrt(dx**2 + dy**2)
                
                # First time initialization
                if self.landing_start_dist == 0:
                    self.landing_start_dist = dist
                
                # Math: Calculate progress ratio (0.0 at IAF -> 1.0 at Threshold)
                # Ensure we don't divide by zero
                denom = max(1.0, self.landing_start_dist)
                progress = max(0.0, min(1.0, (self.landing_start_dist - dist) / denom))
                
                # Glide Slope LERP
                # Speed: Cruise -> 140 kts
                cruise_speed = 250 # Simplified assumption or use initial speed
                self.target_speed = cruise_speed - ((cruise_speed - 140) * progress)
                
                # Altitude: Start Alt -> 0 (Threshold)
                # Assumption: Start Alt is whatever we had at the landing clearance/IAF
                # We'll use 3000 as a standard IAF alt if not set
                start_alt = 3000 
                self.target_alt = start_alt * (1.0 - progress)
                
                # Steering: Head strictly to threshold
                self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                
                # Phase 2: Touchdown Trigger (distance < 100m, alt <= 50ft)
                if dist < 0.1 and self.altitude <= 50:
                    # Check Runway Occupancy Lock
                    runway_status = engine_context.get("runway_status", {})
                    if self.target_runway_id in runway_status:
                        lock = runway_status[self.target_runway_id]
                        if lock["occupied_by"] is None:
                            lock["occupied_by"] = self.callsign
                            self.state = "LANDING"
                            self.target_speed = 0 # Begin rolling stop
                            self.target_alt = 0
                            self.target_heading = self.runway_heading # Lock to runway centerline
                        elif lock["occupied_by"] != self.callsign:
                            # CRASH: Runway Incursion
                            self.state = "CRASHED_RUNWAY_INCURSION"
                            self.speed = 0

            elif self.state == "LANDING":
                # Phase 2 Continued: Rollout
                self.target_speed = 0
                self.target_alt = 0
                self.target_heading = self.runway_heading

            elif self.state == "GO_AROUND":
                # Edge Case: Asleep at the Wheel / Aborted Landing
                self.target_alt = 3000
                self.target_speed = 180
                
                # Find nearest holding fix for recovery
                all_waypoints = engine_context.get("all_waypoints", {})
                if all_waypoints:
                    best_fix = None
                    min_d = float('inf')
                    for wp in all_waypoints.values():
                        if wp.is_iaf: # Pydantic model access
                            d = math.sqrt((wp.x - self.x)**2 + (wp.y - self.y)**2)
                            if d < min_d:
                                min_d = d
                                best_fix = wp
                    
                    if best_fix:
                        self.holding_fix = {"x": best_fix.x, "y": best_fix.y}
                        # If we reached the fix, enter holding
                        if min_d < 1.0:
                            self.state = "HOLDING"
                            self.active_star = None
                            self.wp_index = 0
                
                # Maintain heading until fix is determined
                if not self.holding_fix:
                    self.target_heading = self.runway_heading
                else:
                    dx = self.holding_fix["x"] - self.x
                    dy = self.holding_fix["y"] - self.y
                    self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360

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
                            # Final Waypoint (IAF) Reached
                            self.active_star = None
                            self.wp_index = 0
                            
                            # CHECK: Is there a queued landing?
                            if self.queued_landing:
                                ql = self.queued_landing
                                self.target_runway_id = ql["runway_id"]
                                self.runway_threshold = ql["threshold"]
                                self.runway_heading = ql["runway_heading"]
                                self.state = "APPROACH"
                                self.queued_landing = None # Clear after transition
                            else:
                                # SAFETY CHECK: No instructions after STAR
                                self.state = "GO_AROUND"
        
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
