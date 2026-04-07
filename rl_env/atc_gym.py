# AI Wrapper using Meta OpenEnv (instead of Gymnasium)

from openenv_core import Environment, Space
import numpy as np
from core.engine import SimulationEngine
import math

class ATCEnv(Environment):
    """
    ATC Reinforcement Learning Environment using Meta OpenEnv.
    Wraps the core simulation engine for agent training.
    """
    def __init__(self):
        super().__init__()
        self.engine = SimulationEngine()
        
        # Action space: [Heading, Altitude, Speed] for each aircraft
        # Observation space: Coordinates, Altitude, Heading, Speed of all aircrafts
        # (Define spaces here if needed for OpenEnv)

    def reset(self, seed=None):
        """Reset simulation to initial state"""
        super().reset(seed=seed)
        self.engine = SimulationEngine()
        self.engine.add_aircraft("RL_AC1", "NORTH")
        return self.get_observation(), {}

    def step(self, action):
        """Execute action and advance simulation"""
        # Example action: Apply to one aircraft
        if "RL_AC1" in self.engine.aircrafts:
            ac = self.engine.aircrafts["RL_AC1"]
            # Process discrete actions or continuous vectors
            # This is a placeholder for actual RL logic
            pass
            
        self.engine.step()
        
        obs = self.get_observation()
        reward = self.compute_reward()
        done = False  # End condition logic
        truncated = False
        
        return obs, reward, done, truncated, {}

    def get_observation(self):
        """Get structured observation for LLM/Agent consumption"""
        
        segments_labels = ["North", "North-East", "East", "South-East", 
                           "South", "South-West", "West", "North-West"]
                           
        obs = {
            "aircraft": [],
            "airport_status": {
                "active_runways": list(self.engine.active_runways),
                "runway_occupancy": {},
                "wind": {
                    "heading": int(self.engine.wind_heading),
                    "speed": int(self.engine.wind_speed)
                }
            }
        }
        
        for rw, status in self.engine.runway_status.items():
            obs["airport_status"]["runway_occupancy"][rw] = status.get("occupied_by")
            
        aircraft_list = list(self.engine.aircrafts.values())
        
        for i, ac in enumerate(aircraft_list):
            # Compute position
            distance = round(math.sqrt(ac.x**2 + ac.y**2), 2)
            if ac.x == 0 and ac.y == 0:
                bearing = 0.0
            else:
                bearing = (90 - math.degrees(math.atan2(ac.y, ac.x))) % 360
            segment_idx = round(bearing / 45) % 8
            segment_name = segments_labels[segment_idx]
            
            # Compute separation
            closest_callsign = None
            closest_dist = float('inf')
            conflict_risk = "none"
            
            for j, other_ac in enumerate(aircraft_list):
                if i != j:
                    dist_km = math.sqrt((ac.x - other_ac.x)**2 + (ac.y - other_ac.y)**2)
                    if dist_km < closest_dist:
                        closest_dist = dist_km
                        closest_callsign = other_ac.callsign
                        alt_diff = abs(ac.altitude - other_ac.altitude)
                        if dist_km < 5.0 and alt_diff < 1500:
                            conflict_risk = "high"
                        elif dist_km < 10.0 and alt_diff < 3000 and conflict_risk != "high":
                            conflict_risk = "medium"

            if closest_dist == float('inf'):
                closest_dist_val = None
            else:
                closest_dist_val = round(closest_dist, 2)
                
            # Compute alerts
            alerts = []
            if ac.fuel_level < 10 or ac.emergency_index >= 1:
                alerts.append("low_fuel")
            if ac.emergency_index == 3:
                alerts.append("critical_emergency")
                
            # Intent block additions
            dist_to_thresh = None
            if ac.runway_threshold:
                tx, ty = ac.runway_threshold["x"], ac.runway_threshold["y"]
                dist_to_thresh = round(math.sqrt((tx - ac.x)**2 + (ty - ac.y)**2), 2)

            next_wp = ac.active_star if ac.active_star else "None"
            if hasattr(ac, "direct_to_wp") and ac.direct_to_wp:
                next_wp = ac.direct_to_wp.get("name", "Direct")
                
            ac_obj = {
                "callsign": ac.callsign,
                "position": {
                    "segment": segment_name, 
                    "distance": distance, 
                    "altitude": int(ac.altitude),
                    "target_altitude": int(ac.target_alt)
                },
                "motion": {
                    "heading": round(ac.heading, 1), 
                    "target_heading": round(ac.target_heading, 1),
                    "speed": int(ac.speed),
                    "target_speed": int(ac.target_speed)
                },
                "intent": {
                    "state": ac.state,
                    "assigned_runway": ac.target_runway_id,
                    "distance_to_threshold": dist_to_thresh,
                    "next_waypoint": next_wp
                },
                "alerts": alerts,
                "separation": {
                    "closest_traffic": closest_callsign,
                    "distance": closest_dist_val,
                    "conflict_risk": conflict_risk
                }
            }
            obs["aircraft"].append(ac_obj)
            
        return obs

    def compute_reward(self):
        """Reward function: +1 for distance to runway, -100 for collision"""
        return 0.0
