import salabim as sim
sim.yieldless(False)

class HsimEventWrapper(sim.Component):
    def setup(self, event_delay, action, args, kwargs):
        self.event_delay = event_delay
        self.action = action
        self.args = args
        self.kwargs = kwargs
        
    def process(self):
        if self.event_delay > 0:
            yield self.hold(self.event_delay)
        self.action(*self.args, **self.kwargs)

env = sim.Environment()

def my_hsim_callback(msg):
    print(f"Hsim callback fired at {env.now()} with msg: {msg}")
    if env.now() < 5:
        HsimEventWrapper(event_delay=1, action=my_hsim_callback, args=("Hello again!",), kwargs={})

HsimEventWrapper(event_delay=1, action=my_hsim_callback, args=("Initial!",), kwargs={})
env.run()
