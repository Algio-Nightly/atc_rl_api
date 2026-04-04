# Main simulation loop and state manager

from .aircraft import Aircraft
from .constants import ARRIVAL_GATES

class SimulationEngine:
    def __init__(self, time_step: float = 1.0):
        self.time_step = time_step
        self.aircrafts = {}
        self.simulation_time = 0.0

    def add_aircraft(self, callsign: str, gate_id: str, altitude: float = 15000):
        """Add new aircraft from an arrival gate"""
        pos = ARRIVAL_GATES.get(gate_id, (0, 0))
        # Initial heading towards runway
        self.aircrafts[callsign] = Aircraft(callsign, pos, altitude, heading=180, speed=250)

    def step(self):
        """Advance simulation by one time step"""
        for aircraft in self.aircrafts.values():
            aircraft.update(self.time_step)
        self.simulation_time += self.time_step

    def get_full_state(self):
        """Return global state for API/UI/RL"""
        return {
            "time": self.simulation_time,
            "aircrafts": [a.get_state() for a in self.aircrafts.values()]
        }
