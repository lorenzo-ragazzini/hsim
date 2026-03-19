import salabim as sim
from hsim.core.core.env import Environment

env = Environment()

q = sim.Queue("My Queue")

class MyAgent(sim.Component):
    pass

a1 = MyAgent("A1")
a2 = MyAgent("A2")

def ev1():
    a1.enter(q)
    print("A1 entered at", env.now)

def ev2():
    a2.enter(q)
    print("A2 entered at", env.now)

def ev3():
    a1.leave(q)
    print("A1 left at", env.now)

env.schedule(1, 0, ev1)
env.schedule(3, 0, ev2)
env.schedule(6, 0, ev3)

env.run(10)

q.print_histograms()
q.print_info()
