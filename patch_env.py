import sys, os

with open('hsim/core/core/env.py', 'r') as f:
    env_content = f.read()

import_block = """    
import heapq
import time
from typing import Any, Callable, Optional, Union
from collections import OrderedDict
"""

new_import_block = """    
import sys as _sys, os as _os
_REPO_ROOT = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), "..", "..", "..")
)
if _REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _REPO_ROOT)
import salabim as _salabim

import heapq
import time
from typing import Any, Callable, Optional, Union
from collections import OrderedDict
"""

env_content = env_content.replace(import_block, new_import_block)

new_classes = """

class CompatScheduler:
    \"\"\"
    Drop-in for Scheduler that delegates push/pop to salabim's _event_list.

    Interface consumed by HSim event classes:
        next(scheduler._sequence_generator)   — BaseEvent.__init__
        scheduler.enter(event)                — BaseEvent.add() / trigger()
        scheduler.remove(event)               — BaseEvent.cancel() / trigger()
        scheduler.execute(event)              — executed directly in env.step()
    \"\"\"

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
        \"\"\"Push event to salabim's _event_list as a pure data tuple.\"\"\"
        import heapq
        event._in_queue = True
        if event.time == np.inf:
            self._waiting[id(event)] = event
        else:
            t = max(float(event.time), self._sal_env._now)
            # We push the object natively as a picklable tuple. 
            # In order to let salabim serialize its heap if needed, we might consider formatting,
            # but standard heap pushes are just tuples. Since we are overriding step(), 
            # we just push it in a format salabim ignores or that step() handles.
            # However, salabim might expect format: (time, priority, sequence, component)
            # if we are interleaving with its components. Since we override step(), we'll pop it anyway.
            # To maintain compatibility in case salabim internal functions peek:
            # We will use entirely basic data types.
            sq = next(self._sal_env._item_generator)
            heapq.heappush(
                self._sal_env._event_list,
                (t, float(event.priority), sq, event)
            )
        return event

    def remove(self, event: "Event") -> None:
        \"\"\"Mark event as canceled. (Heap cleanup happens during pop)\"\"\"
        if not event._in_queue:
            return
        if event.time == np.inf:
            self._waiting.pop(id(event), None)
        event._in_queue = False

    def execute(self, event: "Event") -> None:
        \"\"\"Execute event action(s). Identical to Scheduler.execute().\"\"\"
        if callable(event.action):
            try:
                event.action(*event.arguments, **event.kwargs)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Error executing event {event}", exc_info=True
                )
                raise e
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
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(
                        f"Error executing action {idx} of event {event}", exc_info=True
                    )
                    raise e

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
        from hsim.core.core.event import TimedEvent
        return self.enter(TimedEvent(self._env, time, priority, action, argument, **kwargs))

    def delay(self, delay, priority, action=object, argument=(), kwargs={}) -> "Event":
        return self.enterabs(self.timefunc() + delay, priority, action, argument, kwargs)

    def late(self, priority, action, argument=(), kwargs={}) -> "Event":
        return self.enterabs(np.inf, priority, action, argument, kwargs)


class HSimEnvironment(_salabim.Environment):
    \"\"\"
    HSim simulation environment backed by salabim's event scheduler.

    Replaces Environment for salabim-integrated simulations.
    Supports salabim animation and Monitor statistics.
    \"\"\"

    def __init__(self, current_time: bool = False):
        _salabim.yieldless(False)
        super().__init__(trace=False, yieldless=False)

        if current_time:
            import time as _time_mod
            self._now = _time_mod.time()

        self._objects: list = []
        self._agents: OrderedDict = OrderedDict()
        self.counter = Counter()
        self._debug = DEBUG

        self.scheduler = CompatScheduler(self)

    def step(self):
        \"\"\"Override step() to cleanly and synchronously execute HSim events.\"\"\"
        import heapq
        if self._stop:
            raise _salabim.StopSimulation()
        
        if not self._event_list:
            self._now = float('inf')
            raise _salabim.StopSimulation()

        # Look at the top of the heap without popping immediately so we can handle 
        # native salabim processing if it's one of their components.
        # Wait, if we pop, we own it. If we let salabim handle it, we must let super().step() pop it, 
        # but super().step() does NOT take arguments, it pops the next item.
        # So we can peek:
        t, priority, sq, item = self._event_list[0]
        
        # We know if it's our event if it has an `action` attribute (since it's a BaseEvent subclass)
        # However, to be 100% sure without polluting salabim's logic:
        if hasattr(item, "action") and (hasattr(item, "time") or hasattr(item, "priority")):
            # Pop it!
            heapq.heappop(self._event_list)
            self._now = t
            event = item
            
            if getattr(event, "_canceled", False) or not getattr(event, "_in_queue", False):
                return
            event._status = Status.TRIGGERED
            event._in_queue = False
            self.scheduler.execute(event)
            event.process()
        else:
            # It's a native salabim item; let salabim components resume naturally.
            super().step()

    @property
    def now(self) -> float:
        return self._now

    def _time(self) -> float:
        return self._now

    def _sleep(self, delay: float) -> None:
        pass

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
"""

env_content += new_classes

with open('hsim/core/core/env.py', 'w') as f:
    f.write(env_content)
print("done patch")
