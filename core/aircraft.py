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
        
        # Departure & Route Navigation
        self.active_sid = None
        self.active_route = None # List of Point/WP objects
        self.route_index = 0
        
        # Physics constraints
        self.turn_rate = 3.0       # Degrees per second
        self.accel_rate = 2.0      # Knots per second
        self.alt_rate = 25.0       # Feet per second (~1500 fpm)
        self.fuel_burn_rate = 0.01 # Fuel % per second

        # Holding Pattern State
        self.holding_fix = None
        self.holding_radius = 5.0

        self.line_up_timer = 0.0
        
        # Queued Landing State (Delayed Landing)
        self.queued_landing = None # {runway_id, threshold, heading}

    def update(self, dt: float, engine_context: dict = None):
        """Update physics kinematics for the given time step dt"""
        
        if engine_context:
            stars = engine_context.get("stars", {})
            
            # --- PHASE A: GROUND & TAKEOFF ---
            if self.state == "ON_GATE":
                self.target_speed = 0
                self.target_alt = 0
                
            elif self.state == "TAXIING" and self.runway_threshold:
                self.target_speed = 20
                self.target_alt = 0
                dx, dy = self.runway_threshold["x"] - self.x, self.runway_threshold["y"] - self.y
                self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                if math.sqrt(dx**2 + dy**2) < 0.1:
                    self.state = "HOLDING_SHORT"

            elif self.state == "HOLDING_SHORT":
                self.target_speed = 0
                self.target_alt = 0
                if self.runway_threshold:
                    self.x, self.y = self.runway_threshold["x"], self.runway_threshold["y"]
                self.heading = self.target_heading = self.runway_heading
                
            elif self.state == "LINE_UP" and self.runway_threshold:
                self.target_speed = 0
                self.target_alt = 0
                self.x, self.y = self.runway_threshold["x"], self.runway_threshold["y"]
                self.heading = self.target_heading = self.runway_heading
                if self.line_up_timer > 0:
                    self.line_up_timer -= dt
                    if self.line_up_timer <= 0: self.state = "TAKEOFF_ROLL"

            elif self.state == "TAKEOFF_ROLL":
                self.target_speed = 180
                self.target_alt = 0
                self.target_heading = self.runway_heading
                if self.speed >= 160:
                    self.state = "CLIMB_OUT"
                    runway_status = engine_context.get("runway_status", {})
                    if self.target_runway_id in runway_status:
                        lock = runway_status[self.target_runway_id]
                        if lock["occupied_by"] == self.callsign:
                            lock["occupied_by"] = None

            elif self.state == "CLIMB_OUT" and self.active_route:
                if self.route_index < len(self.active_route):
                    target_wp = self.active_route[self.route_index]
                    self.target_alt = target_wp.get("target_alt", 6000)
                    self.target_speed = target_wp.get("target_speed", 250)
                    dx, dy = target_wp["x"] - self.x, target_wp["y"] - self.y
                    self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                    if math.sqrt(dx**2 + dy**2) < 2.0: self.route_index += 1

            # --- PHASE B: ARRIVAL & NAVIGATION ---
            elif self.state == "HOLDING" and self.holding_fix:
                if self.queued_landing:
                    self.state = "ENROUTE"
                    self.holding_fix = None
                else: 
                    fx, fy = self.holding_fix["x"], self.holding_fix["y"]
                    dx, dy = fx - self.x, fy - self.y
                    dist_to_center = math.sqrt(dx**2 + dy**2)
                    angle_from_center = math.degrees(math.atan2(-dy, -dx)) 
                    radial_error = dist_to_center - self.holding_radius
                    heading_offset = 90 - (radial_error * 15) 
                    heading_offset = max(20, min(160, heading_offset))
                    self.target_heading = (90 - (angle_from_center + heading_offset)) % 360

            elif self.direct_to_wp:
                dx, dy = self.direct_to_wp["x"] - self.x, self.direct_to_wp["y"] - self.y
                self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                self.target_alt = self.direct_to_wp["target_alt"]
                self.target_speed = self.direct_to_wp["target_speed"]
                if math.sqrt(dx**2 + dy**2) < 1.5: self.direct_to_wp = None 

            elif self.state == "APPROACH" and self.runway_threshold:
                dx, dy = self.runway_threshold["x"] - self.x, self.runway_threshold["y"] - self.y
                dist = math.sqrt(dx**2 + dy**2)
                if self.landing_start_dist == 0: self.landing_start_dist = dist
                
                # Glidepath LERP (2000ft @ 9km -> 0ft @ 0km)
                progress = max(0.0, min(1.0, (self.landing_start_dist - dist) / max(1.0, self.landing_start_dist)))
                self.target_alt = max(0, 2000 * (1.0 - progress))
                self.target_speed = 180 - (40 * progress)
                self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                
                if dist < 0.2 and self.altitude < 100: # Touchdown Hitbox
                    runway_status = engine_context.get("runway_status", {})
                    if self.target_runway_id in runway_status:
                        lock = runway_status[self.target_runway_id]
                        if lock["occupied_by"] in [None, self.callsign]:
                            lock["occupied_by"] = self.callsign
                            self.state = "LANDING"
                            self.target_speed = 0
                            self.target_alt = 0
                        else:
                            self.state = "CRASHED_RUNWAY_INCURSION"

            elif self.state == "LANDING":
                self.target_speed = 0
                self.target_alt = 0
                self.target_heading = self.runway_heading

            elif (self.state in ["ENROUTE", "GO_AROUND"]) and self.active_star and self.active_star in stars:
                routes = stars[self.active_star]
                if not routes: return
                matching = next((r for r in routes if r["runway"] == self.target_runway_id), routes[0])
                selected_route = matching["waypoints"]
                
                if self.wp_index < len(selected_route):
                    wp = selected_route[self.wp_index]
                    self.target_alt, self.target_speed = wp["target_alt"], wp["target_speed"]
                    dx, dy = wp["x"] - self.x, wp["y"] - self.y
                    self.target_heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
                    
                    if math.sqrt(dx**2 + dy**2) < 2.0 and abs(self.altitude - self.target_alt) < 200:
                        is_iaf = wp.get("is_iaf") or "IAF" in wp.get("name", "")
                        is_faf = wp.get("is_faf") or "FAF" in wp.get("name", "")
                        
                        if is_iaf and not self.queued_landing:
                            self.state = "HOLDING"
                            self.holding_fix = {"x": wp["x"], "y": wp["y"]}
                            return
                        if is_faf and self.queued_landing:
                            ql = self.queued_landing
                            self.target_runway_id, self.runway_threshold, self.runway_heading = ql["runway_id"], ql["threshold"], ql["runway_heading"]
                            self.state, self.landing_start_dist, self.queued_landing = "APPROACH", 0, None
                            return
                        self.wp_index += 1
                        if self.wp_index >= len(selected_route):
                            self.active_star, self.wp_index = None, 0
        
        # 1. Update Heading towards Target
        heading_diff = (self.target_heading - self.heading + 180) % 360 - 180
        if abs(heading_diff) > 0.1:
            turn_step = math.copysign(min(abs(heading_diff), self.turn_rate * dt), heading_diff)
            self.heading = (self.heading + turn_step) % 360

        # 2. Update Speed towards Target
        speed_diff = self.target_speed - self.speed
        if abs(speed_diff) > 0.1:
            eff_accel = self.accel_rate 
            if self.state == "LANDING":
                eff_accel *= 4.0 # Strong braking on touchdown
            accel_step = math.copysign(min(abs(speed_diff), eff_accel * dt), speed_diff)
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
        if not self.state.startswith("CRASHED"):
            rad_heading = math.radians(90 - self.heading)
            v_air_x, v_air_y = self.speed * math.cos(rad_heading), self.speed * math.sin(rad_heading)
            
            wind_h = engine_context.get("wind_heading", 0) if engine_context else 0
            wind_s = engine_context.get("wind_speed", 0) if engine_context else 0
            rad_wind_to = math.radians(90 - (wind_h + 180) % 360)
            v_wind_x, v_wind_y = wind_s * math.cos(rad_wind_to), wind_s * math.sin(rad_wind_to)
            
            vx_ground, vy_ground = v_air_x + v_wind_x, v_air_y + v_wind_y
            
            if self.state in ["HOLDING_SHORT", "LINE_UP", "ON_GATE"]:
                vx_ground = vy_ground = 0
            
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
            KM_PER_DEG_LAT = 111.32
            res["lat"] = round(anchor["lat"] + (self.y / KM_PER_DEG_LAT), 6)
            res["lon"] = round(anchor["lon"] + (self.x / (KM_PER_DEG_LAT * math.cos(math.radians(anchor["lat"])))), 6)
        return res
