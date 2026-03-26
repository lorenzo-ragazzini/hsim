# Plan: Integrate salabim as HSim Scheduler Backend

## Context

HSim currently uses a custom heapq-based scheduler (`Scheduler` in `hsim/core/core/env.py`). The goal is to replace that backend with salabim's `Environment._event_list` so that:
- salabim's animation system (tkinter + PIL) becomes available natively
- salabim's `Monitor` statistics integrate with DES blocks
- All existing HSim FSM, observables, and event classes remain unchanged

Constraints:
- **No greenlets** — salabim runs in `yieldless=False` (generator) mode only
- salabim.py is vendored locally and can be modified
- FSM, observables (reaktiv), and all DES block APIs must remain unchanged
- The existing plain `Environment` class must continue working (backward-compat)

## Architecture

```
HSimEnvironment(salabim.Environment)
    ├── yieldless=False
    ├── scheduler: CompatScheduler        ← drop-in for old Scheduler
    ├── step()                            ← overridden to execute HSim events synchronously
    ├── _agents, activate_fsm()
    └── run(until) → salabim.run(till=N)

CompatScheduler
    ├── _sequence_generator: Counter      ← consumed by BaseEvent.__init__
    ├── _waiting: dict                    ← time==inf events
    ├── enter(event)                      ← creates _HSIMComponent, pushes to _event_list
    ├── remove(event)                     ← marks tuple as canceled
    └── execute(event)                    ← calls event.action(...)

_HSIMComponent(salabim.Component)
    ├── created with process=''           ← no generator, no yield, fully picklable
    ├── setup(evt=event)                  ← stores event
    └── _hsim_run()                       ← standard method (not generator)

# NO yield, NO generators, NO greenlet, FULLY picklable.

HSim Events (BaseEvent, DelayEvent, ConditionedEvent, ...)  ← UNCHANGED
HSim FSM + Observables                                      ← UNCHANGED
HSim DES Blocks (Server, Buffer, Generator, ...)            ← UNCHANGED
```

## Step-by-Step Implementation

### Step 1 — Patch `salabim.py`: guard greenlet import

**File:** `salabim.py` (root of repo)

**Why:** salabim has one bare `import greenlet` inside the animation setup path
(inside `if self.env._yieldless:`). Since we always run `yieldless=False` that branch
never executes at runtime, but some systems fail at module load. Guard it.

**Find** (~line 10663):
```python
        if self.env._yieldless:
            global greenlet
            import greenlet
            self._glet = greenlet.greenlet(self.do_simulate)
```
**Replace with:**
```python
        if self.env._yieldless:
            try:
                global greenlet
                import greenlet
            except ImportError as exc:
                raise ImportError(
                    "greenlet is required for yieldless (greenlet) mode. "
                    "Install with: pip install greenlet"
                ) from exc
            self._glet = greenlet.greenlet(self.do_simulate)
```

**Verify:**
```bash
python -c "import salabim; print('OK')"
```

---

### Step 2 — Add `_sal_component` to `BaseEvent.__slots__`

**File:** `hsim/core/core/event.py`, line 30

**Why:** `CompatScheduler.enter()` sets `event._sal_component = comp`. With
`__slots__`, unlisted attributes raise `AttributeError`.

**Change:**
```python
# Before:
__slots__ = ('env', 'sequence', 'time', 'priority', '_status', 'action', 'arguments',
             'kwargs', '_conditioned', '_canceled', '_should_reset_on_false', '_in_queue')

# After:
__slots__ = ('env', 'sequence', 'time', 'priority', '_status', 'action', 'arguments',
             'kwargs', '_conditioned', '_canceled', '_should_reset_on_false', '_in_queue',
             '_sal_component')
```

No other changes to `event.py`.

**Verify:**
```python
from hsim.core.core.event import BaseEvent
# Cannot test without env yet; just check import succeeds
```

---

### Step 3 — Add repo root to sys.path in `env.py` and import salabim

**File:** `hsim/core/core/env.py`, at the top after existing imports

Add:
```python
import sys as _sys, os as _os
_REPO_ROOT = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), "..", "..", "..")
)
if _REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _REPO_ROOT)
import salabim as _salabim
```

---

### Step 4 — Add `_HSIMComponent` to `env.py`

**File:** `hsim/core/core/env.py`, insert after the `import salabim` block, before `class Scheduler`.

**How it works:**
We wrap HSim events in an `_HSIMComponent(salabim.Component)`. To keep it completely picklable, we use `process=''` so it does **not** create a generator. Then our overridden `HSimEnvironment.step()` detects it, pops it, and synchronously executes normal object methods instead of dealing with execution frames.

```python
class _HSIMComponent(_salabim.Component):
    """
    Bridge: wraps one HSim BaseEvent as a salabim Component.
    No generator/yield is used, making it fully picklable.
    By overriding env.step(), we execute its mapped event synchronously.
    """

    def setup(self, *, evt):
        self._hsim_evt = evt

    def _hsim_run(self):
        # A standard synchronous method, NOT a generator
        evt = self._hsim_evt
        if not getattr(evt, "_canceled", False):
            evt._status = Status.TRIGGERED
            evt._in_queue = False
            evt.env.scheduler.execute(evt)
            evt.process()
```

Note: `Status` must be imported from `hsim.core.core.event`. Add to imports at top of `env.py`:
```python
from hsim.core.core.event import BaseEvent as Event, Status
```
(It may already import `BaseEvent as Event` — just add `Status` to that line.)

---

### Step 5 — Add `CompatScheduler` to `env.py`

**File:** `hsim/core/core/env.py`, after `_HSIMComponent`, before existing `Scheduler`.

```python
class CompatScheduler:
    """
    Drop-in for Scheduler that delegates push/pop to salabim's _event_list.

    Interface consumed by HSim event classes:
        next(scheduler._sequence_generator)   — BaseEvent.__init__
        scheduler.enter(event)                — BaseEvent.add() / trigger()
        scheduler.remove(event)               — BaseEvent.cancel() / trigger()
        scheduler.execute(event)              — _HSIMComponent._hsim_run()
    """

    def __init__(self, sal_env: "HSimEnvironment"):
        self._sal_env = sal_env
        self._waiting: dict = {}               # id(event) → event, for time==inf events
        self._sequence_generator = Counter()
        self._past: list = []
        self.timefunc = lambda: sal_env._now
        self.delayfunc = lambda d: None        # no-op: salabim manages virtual time
        self._env = sal_env

    # -----------------------------------------------------------------------
    # Core interface
    # -----------------------------------------------------------------------

    def enter(self, event: "Event") -> "Event":
        """Push event to salabim's _event_list (or _waiting for time==inf)."""
        event._in_queue = True
        if event.time == np.inf:
            self._waiting[id(event)] = event   # no component needed
        else:
            comp = _HSIMComponent(
                name=f"_hsim_{event.sequence}",
                env=self._sal_env,
                process="",                    # '' → data component, NO generator, picklable
                evt=event,                     # passed to setup()
            )
            event._sal_component = comp
            t = max(float(event.time), self._sal_env._now)
            comp._push(t=t, priority=float(event.priority), urgent=False)
        return event

    def remove(self, event: "Event") -> None:
        """Remove event from wherever it lives."""
        if not event._in_queue:
            return
        if event.time == np.inf:
            self._waiting.pop(id(event), None)
        else:
            comp = getattr(event, "_sal_component", None)
            if comp is not None and comp._on_event_list:
                comp._remove()
            if hasattr(event, "_sal_component"):
                del event._sal_component
        event._in_queue = False

    def execute(self, event: "Event") -> None:
        """Execute event action(s). Identical to Scheduler.execute()."""
        if callable(event.action):
            try:
                event.action(*event.arguments, **event.kwargs)
            except Exception:
                import logging
                logging.getLogger(__name__).error(
                    f"Error executing event {event}", exc_info=True
                )
                raise
        else:
            args = event.arguments
            if len(args) == 0:
                args = [() for _ in range(len(event.action))]
            elif len(args) != len(event.action):
                raise ValueError(
                    f"Arguments ({len(args)}) != actions ({len(event.action)})"
                )
            for idx, action in enumerate(event.action):
                try:
                    action(*args[idx], **event.kwargs)
                except Exception:
                    import logging
                    logging.getLogger(__name__).error(
                        f"Error executing action {idx} of event {event}", exc_info=True
                    )
                    raise

    def cancel(self, event: "Event") -> None:
        event.cancel()

    def cleaner(self) -> None:
        self._waiting = {
            k: e for k, e in self._waiting.items()
            if not getattr(e, "_canceled", False)
        }

    # -----------------------------------------------------------------------
    # Back-compat helpers used by BaseEnvironment.schedule / schedule_absolute
    # -----------------------------------------------------------------------

    def enterabs(self, time, priority, action=object, argument=(), kwargs={}) -> "Event":
        return self.enter(TimedEvent(self._env, time, priority, action, argument, **kwargs))

    def delay(self, delay, priority, action=object, argument=(), kwargs={}) -> "Event":
        return self.enterabs(self.timefunc() + delay, priority, action, argument, kwargs)

    def late(self, priority, action, argument=(), kwargs={}) -> "Event":
        return self.enterabs(np.inf, priority, action, argument, kwargs)
```

---

### Step 6 — Add `HSimEnvironment` to `env.py`

**File:** `hsim/core/core/env.py`, after `CompatScheduler`, before existing `RealTimeEnvironment`.

```python
class HSimEnvironment(_salabim.Environment):
    """
    HSim simulation environment backed by salabim's event scheduler.

    Replaces Environment for salabim-integrated simulations.
    Supports salabim animation and Monitor statistics.

    Usage:
        env = HSimEnvironment()
        # ... add agents, build blocks ...
        env.run(until=100)
        env.run(until=100, animate=True)   # with animation
    """

    def __init__(self, current_time: bool = False):
        # Set yieldless=False BEFORE super().__init__ reads the global flag
        _salabim.yieldless(False)
        super().__init__(trace=False, yieldless=False)

        # HSim bookkeeping (mirrors BaseEnvironment.__init__)
        if current_time:
            import time as _time_mod
            self._now = _time_mod.time()

        self._objects: list = []
        self._agents: OrderedDict = OrderedDict()
        self.counter = Counter()
        self._debug = DEBUG

        # Attach CompatScheduler (replaces Scheduler)
        self.scheduler = CompatScheduler(self)

    def step(self):
        """Override step() to cleanly and synchronously execute HSim events."""
        import heapq
        if self._stop:
            raise _salabim.StopSimulation()
        
        if not self._event_list:
            self._now = float('inf')
            raise _salabim.StopSimulation()

        # Look at the top of the heap without popping
        t, priority, sq, item = self._event_list[0]
        
        if isinstance(item, _HSIMComponent):
            # It's an HSim wrapper component; pop and process synchronously (no generators)
            heapq.heappop(self._event_list)
            self._now = t
            item._status = _salabim.current
            item._on_event_list = False
            item._hsim_run()
        else:
            # It's a native salabim Component; let salabim handle it normally
            super().step()

    # -----------------------------------------------------------------------
    # Time (salabim updates self._now in step(); we just expose it)
    # -----------------------------------------------------------------------

    @property
    def now(self) -> float:
        return self._now

    def _time(self) -> float:
        return self._now

    def _sleep(self, delay: float) -> None:
        pass    # salabim manages virtual time

    # -----------------------------------------------------------------------
    # Agent management (identical to BaseEnvironment)
    # -----------------------------------------------------------------------

    def add_agent(self, obj) -> None:
        count = self.counter()
        key = obj.name if obj.name is not None else count
        self._agents[key] = obj

    def _activate_fsm(self) -> None:
        for ag in self._agents.values():
            ag.activate_fsm()

    # -----------------------------------------------------------------------
    # Scheduling helpers (same signatures as BaseEnvironment)
    # -----------------------------------------------------------------------

    def schedule(self, delay: float, priority: int, action, *args, **kwargs):
        return self.scheduler.delay(delay, priority, action, args, kwargs)

    def schedule_absolute(self, time_: float, priority: int, action, *args, **kwargs):
        return self.scheduler.enterabs(time_, priority, action, args, kwargs)

    # -----------------------------------------------------------------------
    # Run
    # -----------------------------------------------------------------------

    def run(self, until=None) -> None:
        """
        Run the simulation.
        until : float or None — stop at this virtual time; None = run to empty queue.
        """
        self._activate_fsm()
        if until is not None:
            super().run(till=until)
        else:
            super().run()
```

**Update `hsim/core/core/__init__.py`** (if it exists) to export `HSimEnvironment`:
```python
from hsim.core.core.env import HSimEnvironment, Environment, RealTimeEnvironment
```

**Verify the basics:**
```bash
cd /home/lorenzo/GitHub/hsim
python -c "
from hsim.core.core.env import HSimEnvironment
from hsim.core.core.event import DelayEvent
env = HSimEnvironment()
fired = []
DelayEvent(env, delay=5, action=lambda: fired.append(env.now)).add()
env.run(until=10)
assert fired == [5.0], f'Expected [5.0] got {fired}'
print('Step 6 OK — DelayEvent fired at t=5')
"
```

---

### Step 7 — Add salabim Monitor to Queue

**File:** `hsim/core/agent/q.py`

**Why:** salabim Monitor tracks queue length and wait time with time-weighted statistics, integrating with salabim's AnimateMonitor for live charts.

Add at top of file (after existing imports):
```python
try:
    import salabim as _salabim
    _SALABIM_AVAILABLE = True
except ImportError:
    _SALABIM_AVAILABLE = False
```

In `Queue.__init__`, after `self._inbound = dict()`:
```python
        # --- salabim Monitor integration (opt-in when using HSimEnvironment) ---
        self._entry_times: dict = {}    # id(msg) → entry sim time
        if _SALABIM_AVAILABLE and isinstance(env, _salabim.Environment):
            self.queue_length_monitor = _salabim.Monitor(
                name=f"QLen_{id(self)}", level=True, initial_tally=0, env=env
            )
            self.wait_time_monitor = _salabim.Monitor(
                name=f"QWait_{id(self)}", level=False, env=env
            )
        else:
            self.queue_length_monitor = None
            self.wait_time_monitor = None
```

Override `Queue._put` (add after the existing `super()._put(msg)` call):
```python
    def _put(self, msg: Message):
        self._inbound.pop(msg, None)
        msg.reset()
        super()._put(msg)
        msg.receive()
        self._trigger()
        # Monitor: record entry time + update length
        self._entry_times[id(msg)] = self.env.now
        if self.queue_length_monitor is not None:
            self.queue_length_monitor.tally(len(self.queue))
```

Override `Queue.get`:
```python
    def get(self, msg=None) -> Message:
        if msg:
            self.queue.remove(msg)
            self._log_out(msg)
            result = msg
        else:
            result = super().get()
        # Monitor: record wait time + update length
        entry = self._entry_times.pop(id(result), None)
        if entry is not None and self.wait_time_monitor is not None:
            self.wait_time_monitor.tally(self.env.now - entry)
        if self.queue_length_monitor is not None:
            self.queue_length_monitor.tally(len(self.queue))
        return result
```

---

### Step 8 — Create animation package

**File:** `hsim/animation/__init__.py` (new file)

```python
"""
hsim.animation — salabim-backed animation utilities for HSim.

Requires HSimEnvironment (not plain Environment).

Quick start:
    env = HSimEnvironment()
    env.animation_parameters(width=1200, height=700, background_color="20%gray")
    # ... attach AnimateQueueLength, AnimateFSMState, etc. ...
    env.run(until=200)
"""
try:
    import salabim as _sim
    from salabim import (
        AnimateText,
        AnimateRectangle,
        AnimateMonitor,
        AnimateQueue,
        Animate,
    )
    from hsim.animation.helpers import AnimateQueueLength, AnimateFSMState
    _AVAILABLE = True
except ImportError as _e:
    _AVAILABLE = False
    def _missing(*a, **kw):
        raise ImportError("salabim animation requires salabim") from _e
    AnimateText = AnimateRectangle = AnimateMonitor = AnimateQueue = _missing
    Animate = AnimateQueueLength = AnimateFSMState = _missing
```

**File:** `hsim/animation/helpers.py` (new file)

```python
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
            spec=lambda _: (x, y, x + width, y + max(0, len(queue) * height_scale)),
            fillcolor="blue", linecolor="black", env=self._env,
        )
        sim.AnimateText(
            text=lambda _: str(len(queue)),
            x=x + width / 2,
            y=lambda _: y + max(0, len(queue) * height_scale) + 4,
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
            return ", ".join(s.name for s in states) if states else "—"

        sim.AnimateText(text=_state_text, x=x, y=y, env=self._env)
```

---

### Step 9 — Write test file

**File:** `tests/test_scheduler_no_greenlet.py`

```python
"""Integration tests: CompatScheduler / HSimEnvironment backed by salabim."""
import pytest
import numpy as np


def make_env():
    from hsim.core.core.env import HSimEnvironment
    return HSimEnvironment()


class TestInit:
    def test_now_zero(self):
        assert make_env().now == 0.0

    def test_compat_scheduler(self):
        from hsim.core.core.env import CompatScheduler
        assert isinstance(make_env().scheduler, CompatScheduler)

    def test_yieldless_false(self):
        assert make_env()._yieldless is False

    def test_any_yield_true(self):
        assert make_env()._any_yield is True


class TestTimeAdvancement:
    def test_run_until(self):
        env = make_env()
        env.run(until=10)
        assert env.now == pytest.approx(10.0)

    def test_run_empty(self):
        env = make_env()
        env.run()
        assert env.now == pytest.approx(0.0)


class TestDelayEvent:
    def test_fires_at_correct_time(self):
        from hsim.core.core.event import DelayEvent
        env = make_env()
        fired = []
        DelayEvent(env, delay=5, action=lambda: fired.append(env.now)).add()
        env.run(until=10)
        assert fired == [pytest.approx(5.0)]

    def test_order(self):
        from hsim.core.core.event import DelayEvent
        env = make_env()
        order = []
        for d in (7, 2, 5):
            DelayEvent(env, delay=d, action=lambda v=d: order.append(v)).add()
        env.run(until=10)
        assert order == [2, 5, 7]

    def test_canceled_does_not_fire(self):
        from hsim.core.core.event import DelayEvent
        env = make_env()
        fired = []
        evt = DelayEvent(env, delay=3, action=lambda: fired.append(1))
        evt.add()
        evt.cancel()
        env.run(until=10)
        assert fired == []


class TestConditionedEvent:
    def _mock_condition(self):
        from unittest.mock import MagicMock
        cond = MagicMock()
        cond.value = False
        cond.link = MagicMock()
        cond.add_environment = MagicMock()
        cond.unlink = MagicMock()
        cond._sources = []
        cond._targets = []
        cond._unsubscribe_edge = MagicMock()
        return cond

    def test_goes_to_waiting(self):
        from hsim.core.core.event import ConditionedEvent
        env = make_env()
        cond = self._mock_condition()
        evt = ConditionedEvent(env, condition=cond, action=lambda: None)
        evt.add()
        assert id(evt) in env.scheduler._waiting

    def test_trigger_moves_to_event_list(self):
        from hsim.core.core.event import ConditionedEvent
        env = make_env()
        cond = self._mock_condition()
        fired = []
        evt = ConditionedEvent(env, condition=cond, action=lambda: fired.append(env.now))
        evt.add()
        evt.trigger()
        assert id(evt) not in env.scheduler._waiting
        env.run(until=5)
        assert len(fired) == 1


class TestPriority:
    def test_lower_priority_fires_first(self):
        from hsim.core.core.event import TimedEvent
        env = make_env()
        order = []
        TimedEvent(env, time=5, priority=2, action=lambda: order.append("low")).add()
        TimedEvent(env, time=5, priority=1, action=lambda: order.append("high")).add()
        env.run(until=10)
        assert order == ["high", "low"]


class TestQueueMonitor:
    def test_monitors_attached(self):
        from hsim.core.agent.q import Queue
        env = make_env()
        q = Queue(env, capacity=10)
        assert q.queue_length_monitor is not None
        assert q.wait_time_monitor is not None

    def test_length_monitor_tracks(self):
        from hsim.core.agent.q import Queue
        from hsim.core.agent.agent import Agent
        env = make_env()
        q = Queue(env, capacity=10)
        a = Agent(env, name="a")
        q.take(a)
        env.run(until=1)
        assert q.queue_length_monitor.mean() > 0

    def test_wait_time_monitor(self):
        from hsim.core.agent.q import Queue
        from hsim.core.agent.agent import Agent
        env = make_env()
        q = Queue(env, capacity=10)
        a = Agent(env, name="a")
        q.take(a)
        env.run(until=5)
        q.get()
        env.run(until=6)
        assert q.wait_time_monitor.mean() == pytest.approx(5.0)


class TestBackwardCompatibility:
    def test_plain_environment_unchanged(self):
        from hsim.core.core.env import Environment
        from hsim.core.core.event import DelayEvent
        env = Environment()
        fired = []
        DelayEvent(env, delay=3, action=lambda: fired.append(env.now)).add()
        env.run(until=10)
        assert fired == [pytest.approx(3.0)]
```

**Run:**
```bash
cd /home/lorenzo/GitHub/hsim
python -m pytest tests/test_scheduler_no_greenlet.py -v
```

---

## Implementation Order

| # | File | What changes |
|---|------|-------------|
| 1 | `salabim.py` | Guard `import greenlet` |
| 2 | `hsim/core/core/event.py` | Add `_sal_component` to `__slots__` |
| 3 | `hsim/core/core/env.py` | Add salabim import + `_HSIMComponent` |
| 4 | `hsim/core/core/env.py` | Add `CompatScheduler` |
| 5 | `hsim/core/core/env.py` | Add `HSimEnvironment` |
| 6 | `hsim/core/agent/q.py` | Add Monitor integration |
| 7 | `hsim/animation/__init__.py` | New file |
| 8 | `hsim/animation/helpers.py` | New file |
| 9 | `tests/test_scheduler_no_greenlet.py` | New test file |

Steps 1–2 have no dependencies. Steps 3–5 depend on 1–2 (in that order). Steps 6–9 depend on Step 5.

## Verification

### Full end-to-end test
```bash
python -m pytest tests/ -v --tb=short
```

### Manual smoke test with animation
```python
from hsim.core.core.env import HSimEnvironment
from hsim.core.core.event import DelayEvent
env = HSimEnvironment()
env.animation_parameters(width=800, height=400, background_color="white")

import salabim as sim
sim.AnimateText(text=lambda _: f"t = {env.now:.1f}", x=10, y=390, env=env)

DelayEvent(env, delay=5, action=lambda: print(f"Event at t={env.now}")).add()
env.run(until=10)
```

### GSOMGame regression
```bash
python profiler.py
```
All existing tests (test_environment.py, test_agent.py, test_assembly.py, test_generator.py) must pass unchanged.

## Known Challenges

1. **`ConditionedEvent` re-trigger after processed**: If the reaktiv Effect fires `trigger()` after an event has been processed, `trigger()` checks `self.time == np.inf`. After execution, `time` stays at `env.now` (not reset to inf), so `trigger()` is a no-op. This is correct existing behavior.
