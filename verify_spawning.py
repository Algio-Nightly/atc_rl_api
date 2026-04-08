import sys
import os

# Add parent directory to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

from rl_env.environment import ATCEnv
from rl_env.tasks.traffic_pattern import TrafficPatternTask
from rl_env.tasks.storm_traffic import StormTrafficTask
from rl_env.tasks.multi_departure import MultiDepartureTask
from rl_env.tasks.mixed_operations import MixedOperationsTask
from rl_env.models import ATCAction

def verify_task(task_class, expected_final_count, steps_to_run=150):
    print(f"\nVerifying {task_class.__name__}...")
    env = ATCEnv(airport_code="VOCB")
    task = task_class()
    task.setup(env)
    
    initial_count = len(env.engine.aircrafts)
    print(f"Initial count (T=0): {initial_count}")
    
    counts = [initial_count]
    for i in range(steps_to_run):
        obs, reward, done, truncated, info = env.step(ATCAction(commands=[]))
        current_count = len(env.engine.aircrafts)
        if current_count != counts[-1]:
            print(f"Time {env.engine.simulation_time:.1f}s: Count changed to {current_count}")
            counts.append(current_count)
            
    final_count = len(env.engine.aircrafts)
    print(f"Final count after {steps_to_run} steps: {final_count}")
    
    if final_count >= expected_final_count and len(counts) > 1:
        print(f"SUCCESS: {task_class.__name__} is staggered.")
    else:
        print(f"FAILURE: {task_class.__name__} expected {expected_final_count}, got {final_count}")

if __name__ == "__main__":
    verify_task(TrafficPatternTask, 4)
    verify_task(MultiDepartureTask, 3)
    verify_task(StormTrafficTask, 10, steps_to_run=300)
    verify_task(MixedOperationsTask, 6, steps_to_run=250)
