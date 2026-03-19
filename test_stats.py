import salabim as sim
sim.yieldless(False)

env = sim.Environment(trace=True)

class MyAgent(sim.Component):
    def process(self):
        # We don't actually use the process because hsim drives logic via callbacks
        yield self.passivate()
        
agent = MyAgent(name="Worker")

def callback_1():
    agent.set_mode("WORKING")
    print("Agent is now working")
    
def callback_2():
    agent.set_mode("IDLE")
    print("Agent is now idle")
    
class HsimEventWrapper(sim.Component):
    def setup(self, event_delay, action):
        self.event_delay = event_delay
        self.action = action
    def process(self):
        yield self.hold(self.event_delay)
        self.action()

HsimEventWrapper(event_delay=1, action=callback_1)
HsimEventWrapper(event_delay=5, action=callback_2)

env.run(10)
agent.mode.print_histogram(values=True)
