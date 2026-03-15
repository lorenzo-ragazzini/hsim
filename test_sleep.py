import hsim.core.core.env as env_mod
import salabim as sim

class TestEnv(env_mod.Environment):
    def _sleep(self, delay):
        if delay > 0:
            sim.Environment.run(self, duration=delay)
        else:
            sim.Environment.run(self, duration=0)

env = TestEnv()
env.animate(True)
# Add a dummy salabim component to visualize
sim.AnimateRectangle(spec=(-20, -20, 20, 20), x=100, y=100, text="Hsim", arg=env)

# schedule a dump hsim event
def hello():
    print("Hsim event at", env.now)
    env.schedule(1, 0, hello)

env.schedule(1, 0, hello)
env.run(until=10) # this will block in scheduler.run() and call _sleep
