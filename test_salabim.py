import salabim as sim
env=sim.Environment()
class MyAgent(sim.Component):
    def __init__(self, name):
        super().__init__()
        self.name = name
m = MyAgent('test')
env.run(1)
