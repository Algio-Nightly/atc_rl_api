# Aircraft class for physics kinematics

import math

class Aircraft:
    def __init__(self, callsign: str, position: tuple[float, float], altitude: float, heading: float, speed: float):
        self.callsign = callsign
        self.x, self.y = position
        self.altitude = altitude  # Feet
        self.heading = heading  # Degrees
        self.speed = speed  # m/s

    def update(self, dt: float):
        """Update physics kinematics for the given time step dt"""
        # Calculate velocity components
        rad_heading = math.radians(90 - self.heading)
        vx = self.speed * math.cos(rad_heading)
        vy = self.speed * math.sin(rad_heading)

        # Update position
        self.x += vx * dt / 1000  # Convert m to km
        self.y += vy * dt / 1000

    def get_state(self):
        return {
            "callsign": self.callsign,
            "x": self.x,
            "y": self.y,
            "altitude": self.altitude,
            "heading": self.heading,
            "speed": self.speed
        }
