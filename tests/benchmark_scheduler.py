"""
Benchmark: raw-event scheduling (no per-event salabim.Component wrapper).

Measures pure event-loop throughput by scheduling a self-replicating chain of
N events on the salabim-backed Environment, and asserts that no per-event
`_hsim_*` salabim Components are created (the regression the wrapper caused).

Run:  python tests/benchmark_scheduler.py [N]
"""
import sys, os, time, gc, tracemalloc
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from hsim.core.core.env import Environment
from hsim.core.core.event import DelayEvent
import salabim as sim


def run_chain(n_events: int) -> float:
    """Schedule n_events back-to-back (each fires the next). Returns events/sec."""
    env = Environment()
    state = {"i": 0}

    def tick():
        state["i"] += 1
        if state["i"] < n_events:
            DelayEvent(env, delay=1, action=tick).add()

    DelayEvent(env, delay=1, action=tick).add()

    gc.collect()
    t0 = time.perf_counter()
    env.run(until=n_events + 2)
    dt = time.perf_counter() - t0

    assert state["i"] == n_events, f"fired {state['i']} != {n_events}"
    # Core assertion: no per-event Component wrapper leaked into salabim's registry.
    leaked = [c for c in env.components() if c.name().startswith("_hsim_")] \
        if hasattr(env, "components") else []
    assert not leaked, f"{len(leaked)} per-event _hsim_ Components were created!"
    assert "greenlet" not in sys.modules, "greenlet was imported"

    return n_events / dt


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000

    # warmup
    run_chain(2_000)

    tracemalloc.start()
    rate = run_chain(n)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"events           : {n:,}")
    print(f"throughput       : {rate:,.0f} events/sec")
    print(f"peak python mem  : {peak/1e6:.1f} MB  ({peak/n:.0f} bytes/event)")
    print("no _hsim_ Components leaked : OK")
    print("no greenlet imported        : OK")


if __name__ == "__main__":
    main()
