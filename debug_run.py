from rl_env.environment import ATCEnv
from rl_env.models import ATCAction

env = ATCEnv()
obs, _ = env.reset(task="single_approach")
print("Initial observation:", obs)

# Realistic safe sequence
commands = [
    "ATC VECTOR RL001 90",          # turn east toward the runway
    "ATC ALTITUDE RL001 4000",      # descend to 4000 ft
    "ATC SPEED RL001 210",          # set speed to 210 kt
    "ATC LAND RL001 RWY_1"          # request landing
]
action = ATCAction(commands=commands)

obs, reward, done, _, info = env.step(action)
print("After step:", obs, "reward:", reward, "done:", done)
