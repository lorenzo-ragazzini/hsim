# Plan: Make `Environment` extend salabim.Environment (Backward-Compatible)

## Context

The previous step introduced `HSimEnvironment` as a separate class extending `salabim.Environment`. The requirement is that `Environment` itself IS the salabim-backed class — no separate `HSimEnvironment`. All existing code using `from hsim.core.core.env import Environment` gets salabim integration automatically, with zero changes at the call site.

Currently `env.py` has:
- `BaseEnvironment` → base class with heapq scheduler, used by `Environment` and `RealTimeEnvironment`
- `Environment(BaseEnvironment)` → virtual-time env
- `RealTimeEnvironment(BaseEnvironment)` → wall-clock env
- `_HSIMComponent` + `CompatScheduler` + `HSimEnvironment` → the new salabim integration (added by previous step)

**Goal:** Merge `HSimEnvironment` into `Environment`. `Environment` extends `_salabim.Environment` instead of `BaseEnvironment`. Add `HSimEnvironment = Environment` alias for any code that already uses the new name.

## Architecture

```
Environment(salabim.Environment)          ← THE change: no longer extends BaseEnvironment
    ├── yieldless=False, _any_yield=True
    ├── scheduler: CompatScheduler
    ├── _agents, activate_fsm()
    ├── step() override                   ← routes HSim vs salabim events
    └── run(until) → salabim.run(till=N)

HSimEnvironment = Environment            ← alias for backward-compat

BaseEnvironment                          ← kept, only used by RealTimeEnvironment
RealTimeEnvironment(BaseEnvironment)     ← kept unchanged
```

**What doesn't change:** `_HSIMComponent`, `CompatScheduler`, `Scheduler` (old), `BaseEnvironment`, `RealTimeEnvironment`, all FSM/observables/events/DES blocks.

## Step-by-Step Implementation

### Step 1 — Change `Environment` to extend `_salabim.Environment`

**File:** `hsim/core/core/env.py`

Replace the `Environment` class body. Currently it extends `BaseEnvironment`. The new version extends `_salabim.Environment` and incorporates everything from `HSimEnvironment`.

```python
class Environment(_salabim.Environment):
    """
    Virtual-time simulation environment backed by salabim's event scheduler.
    Supports salabim animation and Monitor statistics natively.
    All existing HSim agent/FSM/event code works unchanged.
    """

    def __init__(self, current_time: bool = False):
        _salabim.yieldless(False)
        super().__init__(trace=False, yieldless=False)

        if current_time:
            self._now = time.time()
        # else: salabim already set self._now = 0.0 in super().__init__

        self._objects: list = []
        self._agents: OrderedDict = OrderedDict()
        self.counter = Counter()
        self._debug = DEBUG
        self.scheduler = CompatScheduler(self)

    def step(self):
        """Override step() to execute HSim events synchronously."""
        import heapq
        if not getattr(self, "_event_list", []):
            self.running = False
            return
        t, priority, sq, item, return_val = self._event_list[0]
        if isinstance(item, _HSIMComponent):
            heapq.heappop(self._event_list)
            self._now = t
            item._on_event_list = False
            item._hsim_run()
        else:
            super().step()

    @property
    def now(self) -> float:
        return self._now

    def _time(self) -> float:
        return self._now

    def _sleep(self, delay: float) -> None:
        pass  # salabim manages virtual time

    def add_agent(self, obj) -> None:
        count = self.counter()
        key = obj.name if obj.name is not None else count
        self._agents[key] = obj

    def _activate_fsm(self) -> None:
        for ag in self._agents.values():
            ag.activate_fsm()

    def schedule(self, delay: float, priority: int, action, *args, **kwargs):
        return self.scheduler.delay(delay, priority, action, args, kwargs)

    def schedule_absolute(self, time_: float, priority: int, action, *args, **kwargs):
        return self.scheduler.enterabs(time_, priority, action, args, kwargs)

    def run(self, until=None) -> None:
        self._activate_fsm()
        if until is not None:
            super().run(till=until)
        else:
            super().run()
```

---

### Step 2 — Add `HSimEnvironment` alias and remove old class

**File:** `hsim/core/core/env.py`

After the new `Environment` class, add:
```python
HSimEnvironment = Environment  # backward-compat alias
```

Then **delete** the entire old `HSimEnvironment` class (lines 431–507 in the current file). It is fully replaced by the new `Environment`.

Also update `CompatScheduler.__init__` type hint from `"HSimEnvironment"` to `"Environment"`.

---

### Step 3 — Update tests

**File:** `tests/test_scheduler_no_greenlet.py`

Replace `from hsim.core.core.env import HSimEnvironment` with `from hsim.core.core.env import Environment` everywhere. The `make_env()` helper becomes:

```python
def make_env():
    from hsim.core.core.env import Environment
    return Environment()
```

Also update any `isinstance(env, HSimEnvironment)` checks to `isinstance(env, Environment)`.

---

### Step 4 — Verify Queue monitor still works

`q.py` already checks `isinstance(env, _salabim.Environment)`. Since `Environment` now extends `_salabim.Environment`, this check automatically passes. **No change needed in `q.py`.**

---

## Critical Files

| File | Change |
|------|--------|
| `hsim/core/core/env.py` | `Environment` extends `_salabim.Environment`; delete `HSimEnvironment`; add alias |
| `tests/test_scheduler_no_greenlet.py` | Use `Environment` instead of `HSimEnvironment` |

## Unchanged Files

`hsim/core/core/event.py`, `hsim/core/agent/q.py`, `hsim/animation/`, `salabim.py`, all FSM/DES files — **no changes needed**.

## Verification

```bash
# Basic smoke test — must fire at t=5
python -c "
from hsim.core.core.env import Environment
from hsim.core.core.event import DelayEvent
import salabim as sim
env = Environment()
assert isinstance(env, sim.Environment), 'Not a salabim.Environment!'
fired = []
DelayEvent(env, delay=5, action=lambda: fired.append(env.now)).add()
env.run(until=10)
assert fired == [5.0], f'Expected [5.0] got {fired}'
print('OK — Environment is salabim-backed, no HSimEnvironment needed')
"

# Existing tests must still pass
python -m pytest tests/ -v --tb=short

# Confirm no greenlets
python -c "
from hsim.core.core.env import Environment
import sys
assert 'greenlet' not in sys.modules, 'Greenlet was imported!'
print('OK — no greenlets')
"
