"""
FSM-level throughput benchmark.

Unlike benchmark_scheduler.py (which times raw event scheduling), this measures
a realistic model that pays the full FSM + reaktiv-observable + message cost:
a Generator feeding a Queue that a periodic consumer drains. Reports items
processed per wall-second.

Run:  python tests/benchmark_fsm.py [sim_time]
"""
import sys, os, time, gc
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from hsim.core.core.env import Environment
from hsim.core.core.event import DelayEvent
from hsim.core.des.pymulate import Generator
from hsim.core.agent.q import Queue
from hsim.core.agent.agent import Agent


def run(sim_until=20000, gen_time=1.0, consume_every=1.0):
    env = Environment()
    gen = Generator(env, Agent, serviceTime=gen_time)
    q = Queue(env, capacity=10**9)
    gen.connections["next"] = q
    consumed = [0]

    def consume():
        if len(q.queue):
            q.get(); consumed[0] += 1
        DelayEvent(env, delay=consume_every, action=consume).add()

    DelayEvent(env, delay=consume_every, action=consume).add()
    gc.collect()
    t0 = time.perf_counter()
    env.run(until=sim_until)
    dt = time.perf_counter() - t0
    generated = consumed[0] + len(q.queue)
    return dt, sim_until, generated, consumed[0]


def main():
    sim = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    run(2000)  # warmup
    dt, sim_until, generated, consumed = run(sim)
    print(f"sim_time={sim_until}  wall={dt:.3f}s")
    print(f"items generated={generated}  consumed={consumed}")
    print(f"throughput: {generated/dt:,.0f} items/s")


if __name__ == "__main__":
    main()
