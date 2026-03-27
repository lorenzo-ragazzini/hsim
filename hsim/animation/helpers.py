"""HSim-specific composite animation helpers."""
from __future__ import annotations
import salabim as sim

class AnimateQueueLength:
    """
    Live bar + monitor plot for an HSim Queue.

    Parameters
    ----------
    queue : hsim.core.agent.q.Queue
    x, y  : position of bar left-bottom corner
    width : bar width in pixels
    height_scale : pixels per item
    env   : HSimEnvironment (default: queue.env)
    """

    def __init__(self, queue, x=50, y=50, width=20, height_scale=10, env=None):
        self._q = queue
        self._env = env or queue.env

        sim.AnimateRectangle(
            spec=lambda _: (x, y, x + width, y + max(0, len(queue.queue) * height_scale)),
            fillcolor="blue", linecolor="black", env=self._env,
        )
        sim.AnimateText(
            text=lambda _: str(len(queue.queue)),
            x=x + width / 2,
            y=lambda _: y + max(0, len(queue.queue) * height_scale) + 4,
            anchor="s", env=self._env,
        )
        if getattr(queue, "queue_length_monitor", None) is not None:
            sim.AnimateMonitor(
                monitor=queue.queue_length_monitor,
                x=x + width + 10, y=y, width=200, height=80, env=self._env,
            )

class AnimateFSMState:
    """
    Text label showing an agent's current FSM state.

    Parameters
    ----------
    agent    : any HSim Agent with a .stateMachine attribute
    x, y     : label position
    fsm_name : attribute name of the FSM (default "stateMachine")
    env      : HSimEnvironment (default: agent.env)
    """

    def __init__(self, agent, x=50, y=50, fsm_name="stateMachine", env=None):
        self._agent = agent
        self._env = env or agent.env
        self._fsm_name = fsm_name

        def _state_text(_):
            fsm = getattr(agent, fsm_name, None)
            if fsm is None:
                return "—"
            states = fsm._current_state.value
            if not isinstance(states, (list, tuple, set)):
                states = [states] if states else []
            return ", ".join(s.name for s in states if s) if states else "—"

        sim.AnimateText(text=_state_text, x=x, y=y, env=self._env)