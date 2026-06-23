"""
Live salabim visualization for the FSM-based HSim pipeline.

Builds  Generator -> Queue -> (periodic consumer)  and attaches the
salabim-backed animation helpers (AnimateQueueLength, AnimateFSMState) from
hsim/animation. The FSM/DES architecture is unchanged; salabim provides the
animation window + Monitor statistics on top of HSim's own event scheduler.

Run:
    python examples/animation_demo.py            # opens the salabim window
    python examples/animation_demo.py --check      # headless verify + frame.png (CI / no display)

The salabim window shows:
    * a live clock (salabim built-in, top-right),
    * the generator's current FSM state (text label),
    * the queue length as a growing/shrinking bar with a count,
    * a salabim Monitor plot of queue length over time.
"""
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import salabim as _sim
from hsim.core.core.env import Environment
from hsim.core.core.event import DelayEvent
from hsim.core.des.pymulate import Generator
from hsim.core.agent.q import Queue
from hsim.core.agent.agent import Agent
from hsim.animation.helpers import AnimateQueueLength, AnimateFSMState


def build_model(gen_time=1.5, consume_every=2.5):
    """Generator -> Queue with a periodic consumer. Returns (env, gen, queue).

    A consumer pulls one item every `consume_every` so the queue length
    oscillates -- keeping the bar, the count and the Monitor plot dynamic, and
    exercising both the queue-length and wait-time Monitors. Any HSim FSM block
    (Server, Buffer, Assembly, ...) animates the same way.
    """
    env = Environment()
    gen = Generator(env, Agent, serviceTime=gen_time)
    queue = Queue(env, capacity=1000)
    gen.connections["next"] = queue

    def consume():
        if len(queue.queue):
            queue.get()                       # records wait-time + updates length Monitor
        DelayEvent(env, delay=consume_every, action=consume).add()

    DelayEvent(env, delay=consume_every, action=consume).add()
    return env, gen, queue


def attach_animations(env, gen, queue, show_monitor=True):
    """Attach the hsim.animation helpers + a couple of static captions."""
    _sim.AnimateText("HSim FSM pipeline (Generator -> Queue) on salabim",
                     x=50, y=560, fontsize=20, env=env)
    _sim.AnimateText("generator FSM state:", x=50, y=470, fontsize=12, env=env)
    AnimateFSMState(gen, x=50, y=445)
    _sim.AnimateText("queue length:", x=50, y=360, fontsize=12, env=env)
    AnimateQueueLength(queue, x=50, y=100, width=40, height_scale=14,
                       show_monitor=show_monitor)


# ----------------------------------------------------------------------------
# Live salabim window (default)
# ----------------------------------------------------------------------------

def run_live():
    env, gen, queue = build_model()
    env.animation_parameters(
        animate=True, synced=True, speed=6,
        width=1000, height=600, background_color="20%gray",
        title="HSim FSM Demo", show_fps=False,
    )
    attach_animations(env, gen, queue, show_monitor=True)
    env.run(until=120)


# ----------------------------------------------------------------------------
# Headless verification (--check): no display needed
# ----------------------------------------------------------------------------

def run_check():
    env, gen, queue = build_model()
    env.animation_parameters(
        animate=False, width=1000, height=600,
        background_color="20%gray", title="HSim FSM Demo",
    )
    # Skip the AnimateMonitor panel: it needs the live tick to init and cannot
    # be captured offscreen. The live window includes it.
    attach_animations(env, gen, queue, show_monitor=False)

    samples = []

    def sample():
        states = gen.stateMachine._current_state.value
        names = ",".join(s.name for s in states) if states else "-"
        samples.append((round(env.now, 2), names, len(queue.queue)))
        if env.now < 40:
            DelayEvent(env, delay=2, action=sample).add()

    DelayEvent(env, delay=1, action=sample).add()
    env.run(until=42)

    qmon, wmon = queue.queue_length_monitor, queue.wait_time_monitor
    print("=== Headless visualization verification ===")
    for s in samples[:10]:
        print(f"   t={s[0]:<5} gen_state={s[1]:<10} qlen={s[2]}")
    assert qmon is not None, "queue_length_monitor not created (env not salabim-backed?)"
    assert qmon.maximum() >= 1, "queue_length_monitor recorded no growth"
    assert all(st and st != "-" for _, st, _ in samples), "FSM state label was empty"
    print(f"queue_length_monitor (level): mean={qmon.mean():.3f}, max={qmon.maximum():.0f}")
    print(f"wait_time_monitor: {wmon.number_of_entries()} entries, "
          f"mean={wmon.mean():.3f}" if wmon.number_of_entries() else
          "wait_time_monitor: 0 entries")

    out = os.path.join(os.path.dirname(__file__), "frame.png")
    try:
        _sim.can_animate(try_only=True)   # lazily import PIL into salabim globals
        env._t = env.now
        env._capture_image(video_mode="2d").save(out)
        print(f"rendered frame -> {out}")
    except Exception as e:
        print(f"frame render skipped ({type(e).__name__}: {e})")
    print("OK -- salabim visualization wired to the FSM pipeline.")


if __name__ == "__main__":
    if "--check" in sys.argv:
        run_check()
    else:
        run_live()
