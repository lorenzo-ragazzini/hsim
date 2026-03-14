import cProfile
from hsim.core.des.pymulate import Environment, Generator, Terminator
from hsim.core.agent.agent import Agent
def main():
    env = Environment()
    g = Generator(env, agent_function=Agent, serviceTime=1)
    g.connections["next"] = Terminator(env, "T")
    env.run(10)
cProfile.run("main()")
