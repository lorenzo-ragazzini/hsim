import salabim as sim
from hsim.core.core.env import Environment

# hsim Environment
env = Environment()

# dummy agent
class MyAgent(sim.Component):
    pass

# We create the agent
agent = MyAgent(name="HybridWorker")

def callback_1():
    agent.set_mode("WORKING")
    print("Agent is working at", env.now)
    env.schedule(4, 0, callback_2)

def callback_2():
    agent.set_mode("IDLE")
    print("Agent is idle at", env.now)

# schedule hsim event
env.schedule(1, 0, callback_1)

# run hsim
env.run(10)

agent.mode.print_histogram(values=True)
