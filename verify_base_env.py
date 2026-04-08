import sys
import os

# Add parent directory to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

from rl_env.environment import ATCEnv
from rl_env.models import ATCAction

def verify_base_env():
    print("\nVerifying Base ATCEnv with multi_departure config...")
    env = ATCEnv(airport_code="VOCB")
    
    # Use the default multi_departure config (not the task class)
    obs, info = env.reset(task="multi_departure")
    
    initial_count = len(env.engine.aircrafts)
    print(f"Initial count (T=0): {initial_count}")
    
    for i in range(100):
        env.step(ATCAction(commands=[]))
        current_count = len(env.engine.aircrafts)
        if i % 30 == 0 and i > 0:
            print(f"Time {env.engine.simulation_time}s: Count is {current_count}")
            
    final_count = len(env.engine.aircrafts)
    print(f"Final count: {final_count}")
    
    if final_count == 3:
        print("SUCCESS: Base ATCEnv now supports staggered departures.")
    else:
        print(f"FAILURE: Expected 3, got {final_count}")

if __name__ == "__main__":
    verify_base_env()
