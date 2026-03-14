#!/usr/bin/env python3
"""HSIM-first simulation with salabim visualization bridge.

This script keeps HSIM as the source of truth for runtime behavior:
- HGenerator/HBuffer/HServer/HTerminator execute the model.
- Station coordinates are attached to HSIM component instances.
- Salabim is only the animation layer, mirroring HSIM queue/state in real time.
"""

import argparse

import salabim as sim

from hsim.core.core.env import Environment as HEnvironment
from hsim.core.des.pymulate import (
    Buffer as HBuffer,
    Generator as HGenerator,
    Server as HServer,
    Terminator as HTerminator,
)
from hsim.core.des.trajectory import TrajectoryCircle, TrajectoryMerged, TrajectoryPolygon


class SimAgent(sim.Component):
    """HSIM item type derived from salabim Component, as requested."""

    def __lt__(self, other):
        # HSIM message queues rely on sortable content comparisons.
        return False


class VisualToken(sim.Component):
    """Salabim-only token used to render mirrored HSIM queue contents."""

    def setup(self, color="orange"):
        self.color = color

    def animation_objects(self, id=None):
        # salabim expects an iterable of animation objects here.
        return [sim.AnimateCircle(radius=0.55, fillcolor=self.color, linecolor="white", linewidth=1)]


class HSIMSalabimBridge(sim.Component):
    """Advance HSIM in fixed steps and synchronize salabim visual objects."""

    def setup(self, h_env, h_blocks, mirror_queues, state, dt=0.15):
        self.h_env = h_env
        self.h_blocks = h_blocks
        self.mirror_queues = mirror_queues
        self.state = state
        self.dt = dt
        self.tokens = {name: [] for name in mirror_queues.keys()}

    def _sync_queue_len(self, q_name, target_len):
        q = self.mirror_queues[q_name]
        cur_tokens = self.tokens[q_name]

        while len(cur_tokens) < target_len:
            token = VisualToken(color="#f59e0b" if q_name == "GEN_BUF" else "#38bdf8")
            token.enter(q)
            cur_tokens.append(token)

        while len(cur_tokens) > target_len:
            token = cur_tokens.pop()
            token.cancel()

    def process(self):
        # Repeatedly advance HSIM virtual clock and mirror the latest state.
        while True:
            target = self.h_env.now + self.dt
            self.h_env.run(until=target)

            gen = self.h_blocks["GEN"]
            buf = self.h_blocks["BUF"]
            srv = self.h_blocks["SRV"]
            snk = self.h_blocks["SNK"]

            gen_buf_len = len(buf.store)
            buf_srv_len = len(srv.store)
            done_len = len(snk.store)

            self._sync_queue_len("GEN_BUF", gen_buf_len)
            self._sync_queue_len("BUF_SRV", buf_srv_len)

            self.state["h_time"] = self.h_env.now
            self.state["gen_buf_len"] = gen_buf_len
            self.state["buf_srv_len"] = buf_srv_len
            self.state["done_len"] = done_len
            self.state["srv_state"] = srv.stateMachine.current_state[0].name

            self.hold(self.dt)


class Reporter(sim.Component):
    """Periodic terminal snapshot to prove HSIM-driven dynamics."""

    def setup(self, state, step=5.0, till=60.0):
        self.state = state
        self.step = step
        self.till = till

    def process(self):
        while self.env.now() <= self.till:
            print(
                f"t={self.env.now():6.2f} | h_t={self.state.get('h_time', 0.0):6.2f} | "
                f"GEN->BUF={self.state.get('gen_buf_len', 0):3d} | "
                f"BUF->SRV={self.state.get('buf_srv_len', 0):3d} | "
                f"DONE={self.state.get('done_len', 0):3d} | "
                f"SRV={self.state.get('srv_state', 'n/a')}"
            )
            self.hold(self.step)


def build_hsim_model():
    """Build HSIM components and attach station coordinates to HSIM objects."""
    h_env = HEnvironment()

    def _make_agent(gen_self):
        return SimAgent(name=f"part.{gen_self._counter + 1}")

    gen = HGenerator(h_env, name="GEN", agent_function=_make_agent, serviceTime=0.85)
    buf = HBuffer(h_env, name="BUF", capacity=8)
    srv = HServer(h_env, name="SRV", serviceTime=1.35)
    snk = HTerminator(h_env, name="SNK")

    gen.connections["next"] = buf
    buf.connections["next"] = srv
    srv.connections["next"] = snk

    # Coordinates live on HSIM components (source of truth for layout)
    gen.x, gen.y = 10, 38
    buf.x, buf.y = 38, 38
    srv.x, srv.y = 66, 38
    snk.x, snk.y = 90, 38

    blocks = {"GEN": gen, "BUF": buf, "SRV": srv, "SNK": snk}
    return h_env, blocks


def draw_layout(blocks, state):
    """Draw station boxes and dynamic labels from HSIM-backed state."""
    sim.AnimateRectangle(spec=(2, 8, 98, 52), fillcolor="#0f172a", linecolor="#334155", linewidth=3)

    for blk in blocks.values():
        x0, y0, x1, y1 = blk.x - 6, blk.y - 3, blk.x + 6, blk.y + 3
        sim.AnimateRectangle(spec=(x0, y0, x1, y1), fillcolor="#1e293b", linecolor="#64748b", linewidth=2)
        sim.AnimateText(text=blk.name, x=blk.x - 4.5, y=blk.y + 1.3, textcolor="#e2e8f0", fontsize=10, xy_anchor="sw")

    sim.AnimateText(text="HSIM runtime + salabim animation bridge", x=3, y=53.5, textcolor="#f8fafc", fontsize=13, xy_anchor="sw")

    sim.AnimateText(
        text=lambda t: f"HSIM time: {state.get('h_time', 0.0):.2f}",
        x=3,
        y=4,
        textcolor="#cbd5e1",
        fontsize=11,
        xy_anchor="sw",
    )
    sim.AnimateText(
        text=lambda t: f"GEN->BUF: {state.get('gen_buf_len', 0)}",
        x=24,
        y=4,
        textcolor="#a7f3d0",
        fontsize=11,
        xy_anchor="sw",
    )
    sim.AnimateText(
        text=lambda t: f"BUF->SRV: {state.get('buf_srv_len', 0)}",
        x=44,
        y=4,
        textcolor="#a7f3d0",
        fontsize=11,
        xy_anchor="sw",
    )
    sim.AnimateText(
        text=lambda t: f"SRV state: {state.get('srv_state', 'n/a')}",
        x=64,
        y=4,
        textcolor="#bae6fd",
        fontsize=11,
        xy_anchor="sw",
    )


def build_agv_animation():
    """AGV animation from HSIM trajectory classes."""
    loop = TrajectoryPolygon([(10, 14), (90, 14), (90, 30), (10, 30), (10, 14)], vmax=10)
    arc = TrajectoryCircle(center=(50, 22), radius=8, vmax=8, angle_start=0, angle_end=360)
    merged = TrajectoryMerged([loop, arc])

    sim.AnimateCircle(
        radius=1.2,
        x=lambda t: loop.position(t % max(loop.duration, 1e-6))[0],
        y=lambda t: loop.position(t % max(loop.duration, 1e-6))[1],
        fillcolor="#f59e0b",
        linecolor="#e2e8f0",
        linewidth=2,
        text="AGV-1",
        textcolor="#f8fafc",
        text_offsety=2.0,
        fontsize=9,
    )

    sim.AnimateCircle(
        radius=1.2,
        x=lambda t: merged.position(t % max(merged.duration, 1e-6))[0],
        y=lambda t: merged.position(t % max(merged.duration, 1e-6))[1],
        fillcolor="#38bdf8",
        linecolor="#e2e8f0",
        linewidth=2,
        text="AGV-2",
        textcolor="#f8fafc",
        text_offsety=2.0,
        fontsize=9,
    )


def main():
    parser = argparse.ArgumentParser(description="Run HSIM-first model with salabim animation.")
    parser.add_argument("--headless", action="store_true", help="Run without GUI and print snapshots.")
    parser.add_argument("--duration", type=float, default=120.0, help="Simulation duration.")
    args = parser.parse_args()

    sim.yieldless(True)

    env = sim.Environment(
        trace=False,
        animate=not args.headless,
        speed=8,
        title="hsim | salabim bridge animation",
        width=1280,
        height=760,
        x0=0,
        y0=0,
        x1=100,
        show_time=True,
        background_color="#0b1220",
        blind_animation=args.headless,
    )

    h_env, blocks = build_hsim_model()

    # Salabim queues are mirror views; HSIM components are the actual model.
    q_gen_buf_mirror = sim.Queue("q_gen_buf_mirror")
    q_buf_srv_mirror = sim.Queue("q_buf_srv_mirror")

    state = {
        "h_time": 0.0,
        "gen_buf_len": 0,
        "buf_srv_len": 0,
        "done_len": 0,
        "srv_state": "Starving",
    }

    bridge = HSIMSalabimBridge(
        h_env=h_env,
        h_blocks=blocks,
        mirror_queues={"GEN_BUF": q_gen_buf_mirror, "BUF_SRV": q_buf_srv_mirror},
        state=state,
        dt=0.15,
    )
    bridge.activate()

    if not args.headless:
        draw_layout(blocks=blocks, state=state)
        build_agv_animation()

        # Native salabim queue animations fed by HSIM queue lengths.
        q_gen_buf_mirror.animate(x=16, y=33, direction="e", max_length=10)
        q_buf_srv_mirror.animate(x=44, y=33, direction="e", max_length=10)

    if args.headless:
        Reporter(state=state, step=5.0, till=args.duration).activate()

    env.run(till=args.duration)

    if args.headless:
        print("\nFinal HSIM-backed state")
        print(f"HSIM time={state['h_time']:.2f}")
        print(f"GEN->BUF={state['gen_buf_len']}")
        print(f"BUF->SRV={state['buf_srv_len']}")
        print(f"DONE={state['done_len']}")
        print(f"SRV state={state['srv_state']}")


if __name__ == "__main__":
    main()
