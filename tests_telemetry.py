import sys
import os
import json
import math

# Add the project root to sys.path
sys.path.append(os.getcwd())

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction

def test_telemetry():
    print("--- Starting LLM-Native Telemetry Test ---")
    env = ATCEnv(airport_code="VOCB")
    
    # Reset returns JSON string
    print("\n[1] Verifying Reset (Initial Telemetry)...")
    telemetry_str = env.reset(task="single_approach")
    assert isinstance(telemetry_str, str), "Reset should return a raw JSON string"
    
    telemetry = json.loads(telemetry_str)
    assert "step_telemetry" in telemetry, "Telemetry missing key 'step_telemetry'"
    aircraft = telemetry["step_telemetry"]["aircraft_metrics"]
    assert len(aircraft) > 0, "No aircraft metrics found"
    
    ac = aircraft[0]
    print(f"Callsign: {ac['callsign']}")
    print(f"Initial Severity Index: {ac['severity_index']}")
    assert ac["severity_index"] == 1.0, "Initial severity should be 1.0"
    
    # 2. Test Command Rejection
    print("\n[2] Testing Command Rejection Tracking...")
    # Try to TAXI while ENROUTE
    action = ATCAction(commands=[f"ATC TAXI {ac['callsign']} RWY_1"])
    response_str = env.step(action)
    assert isinstance(response_str, str), "Step should return a raw JSON string"
    
    telemetry = json.loads(response_str)
    ac_telemetry = next(a for a in telemetry["step_telemetry"]["aircraft_metrics"] if a["callsign"] == ac["callsign"])
    print(f"Rejections: {ac_telemetry['command_rejections']}")
    assert len(ac_telemetry["command_rejections"]) > 0, "Rejection not logged"
    assert "Must be ON_GATE" in ac_telemetry["command_rejections"][0]
    
    # 3. Test Time & State Tracking
    print("\n[3] Testing Time & State Tracking...")
    # Advance 10 steps
    for _ in range(9):
        env.step(ATCAction(commands=[]))
    
    response_str = env.step(ATCAction(commands=[]))
    telemetry = json.loads(response_str)
    ac_telemetry = next(a for a in telemetry["step_telemetry"]["aircraft_metrics"] if a["callsign"] == ac["callsign"])
    
    print(f"Total Time Active: {ac_telemetry['timing_stats']['total_time_active_sec']}")
    assert ac_telemetry["timing_stats"]["total_time_active_sec"] >= 11, "Time tracking failed"
    
    # 4. Test Safety Metrics
    print("\n[4] Testing Safety Metrics...")
    ac_obj = env.engine.aircrafts[ac["callsign"]]
    env.engine.add_aircraft(
        callsign="BOT_CONFLICT",
        ac_type="B737",
        weight_class="Medium",
        gate="N",
        altitude=ac_obj.altitude,
        heading=ac_obj.heading,
        speed=ac_obj.speed
    )
    conflict_ac = env.engine.aircrafts["BOT_CONFLICT"]
    conflict_ac.x, conflict_ac.y = ac_obj.x + 1.0, ac_obj.y + 1.0
    
    response_str = env.step(ATCAction(commands=[]))
    telemetry = json.loads(response_str)
    ac_telemetry = next(a for a in telemetry["step_telemetry"]["aircraft_metrics"] if a["callsign"] == ac["callsign"])
    
    print(f"Separation Warnings: {ac_telemetry['safety_metrics']['separation_warnings_triggered']}")
    assert ac_telemetry["safety_metrics"]["separation_warnings_triggered"] > 0, "Separation warning not tracked"
    
    # 5. Test Severity Index (Base-2 capped formula)
    print("\n[5] Testing Severity Index Scaling...")
    ac_obj.fuel_level = 5.0 # Trigger emergency
    env.step(ATCAction(commands=[]))
    
    # Advance 40 seconds
    for _ in range(39):
        env.step(ATCAction(commands=[]))
        
    response_str = env.step(ATCAction(commands=[]))
    telemetry = json.loads(response_str)
    ac_telemetry = next(a for a in telemetry["step_telemetry"]["aircraft_metrics"] if a["callsign"] == ac["callsign"])
    
    # 40 seconds = 4 sets of 10s. Base-2 should be roughly 2^4 = 16
    print(f"Emergency Timer: {ac_obj.emergency_timer}")
    print(f"Severity Index: {ac_telemetry['severity_index']}")
    # 2^(40/10) = 2^4 = 16.0
    assert 15.0 < ac_telemetry["severity_index"] < 17.0, f"Severity index scaling incorrect: {ac_telemetry['severity_index']}"
    
    # 6. Test Metric Flushing
    print("\n[6] Testing Metric Flushing...")
    del env.engine.aircrafts["BOT_CONFLICT"]
    response_str = env.step(ATCAction(commands=[]))
    telemetry = json.loads(response_str)
    ac_telemetry = next(a for a in telemetry["step_telemetry"]["aircraft_metrics"] if a["callsign"] == ac["callsign"])
    assert len(ac_telemetry["command_rejections"]) == 0, "Rejections not flushed"
    assert ac_telemetry["safety_metrics"]["separation_warnings_triggered"] == 0, "Safety metrics not flushed"

    print("\n--- LLM-NATIVE TELEMETRY TEST PASSED ---")

if __name__ == "__main__":
    try:
        test_telemetry()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
