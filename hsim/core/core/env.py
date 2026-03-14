if __name__ == "__main__":
    import sys
    import os
    # Cross-platform path handling
    abs_path = os.path.abspath(__file__)
    parts = abs_path.split(os.sep)
    if "hsim" in parts:
        hsim_index = parts.index("hsim")
        hsim_path = os.sep.join(parts[:hsim_index + 1])
        if hsim_path not in sys.path:
            sys.path.append(hsim_path)

    
import heapq
import time
from typing import Any, Callable, Optional, Union
from collections import OrderedDict

import numpy as np
from hsim.core.core.event import BaseEvent as Event, Status
from hsim.core.core.event import TimedEvent
import salabim as sim

DEBUG = False



class Scheduler():
    def __init__(self, timefunc: Callable[[], float], delayfunc: Callable[[float], None], env:'Environment'):
        self._lock = Context()
        self._past = list()
        self._env = env
        self._queue = []                   # heapq: (time, priority, neg_sequence, event)
        self._waiting = {}                 # dict[id(event) -> event], for time==inf events
        self._sequence_generator = Counter()
        self.timefunc = timefunc
        self.delayfunc = delayfunc
    def enter(self, event: 'Event') -> 'Event':
        event._in_queue = True
        if event.time == np.inf:
            self._waiting[id(event)] = event
        else:
            heapq.heappush(self._queue, (event.time, event.priority, -event.sequence, event))
        return event
    def remove(self, event: 'Event') -> None:
        """Remove event from whichever collection it's in. Call BEFORE mutating event.time."""
        if not event._in_queue:
            return
        if event.time == np.inf:
            self._waiting.pop(id(event), None)
        else:
            # O(n) — only called for rescheduling, not hot path
            self._queue = [(t, p, s, e) for t, p, s, e in self._queue if e is not event]
            heapq.heapify(self._queue)
        event._in_queue = False
    def enterabs(self, time, priority, action=object, argument=(), kwargs={}) -> 'Event':
        return self.enter(TimedEvent(self._env, time, priority, action, argument, **kwargs))
    def delay(self, delay, priority, action=object, argument=(), kwargs={}) -> 'Event':
        """Schedule event after delay seconds."""
        return self.enterabs(self.timefunc() + delay, priority, action, argument, kwargs)
    def late(self, priority, action, argument=(), kwargs={}):
        """Schedule event at infinite time (waiting)."""
        return self.enterabs(np.inf, priority, action, argument, kwargs)
    def run(self, blocking=True):
        delayfunc, timefunc, lock, past = self.delayfunc, self.timefunc, self._lock, self._past
        while self._queue:
            _, _, _, event = heapq.heappop(self._queue)  # Unpack 4-tuple: (time, priority, neg_sequence, event)
            event._in_queue = False
            if getattr(event, "_canceled", False):
                continue
            elif event.time == np.inf:
                continue
            delayfunc(event.time - timefunc())
            if event.pending:
                event.time = np.inf
                event.schedule()
                self.enter(event)
            elif "StopSimulation" in event.kwargs:
                return
            else:
                # if event._conditioned:
                #     if not event.verify():
                #         event._status, event.time = Status.CONDITIONED, np.inf
                #         event.add()
                #         continue
                event.trigger()
                self.execute(event)
                # delayfunc(0)
                past.append(event)
                event.process()
    def execute(self,event):
        """
        Execute event action(s).
        
        Args:
            event: Event to execute
        """
        if callable(event.action):
            try:
                event.action(*event.arguments, **event.kwargs)
            except Exception as e:
                if DEBUG:
                    # Re-raise in debug mode to see full traceback
                    raise
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error executing event {event}: {e}", exc_info=True)
                    raise
        else:
            if len(event.arguments) == 0:
                event.arguments = [() for _ in range(len(event.action))]
            elif len(event.arguments) != len(event.action):
                raise ValueError(f"Arguments count ({len(event.arguments)}) does not match actions count ({len(event.action)})")
            for index, action in enumerate(event.action):
                try:
                    action(*event.arguments[index], **event.kwargs)
                except Exception as e:
                    if DEBUG:
                        raise
                    else:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error executing action {index} of event {event}: {e}", exc_info=True)
                        raise 
    def cancel(self, event):
        # Just flag as canceled, do not remove from queue
        event.cancel()

    def cleaner(self):
        # Remove all canceled events from the queue
        self._queue = [(t, p, s, e) for t, p, s, e in self._queue
                       if not getattr(e, "_canceled", False)]
        heapq.heapify(self._queue)
        self._waiting = {k: e for k, e in self._waiting.items()
                         if not getattr(e, "_canceled", False)}
        
class Context:
    def __enter__(self):
        pass
    def __exit__(self,a,b,c):
        pass

class Counter():
    def __init__(self, value=0):
        super().__init__()
        self._value = value
    def __call__(self):
        return self.__next__()
    def __next__(self):
        self._value += 1
        return self._value
    def __repr__(self) -> str:
        return "Counter({self.val})".format(self._value)
    
class BaseEnvironment(sim.Environment):
    """
    Base class for simulation environments.
    
    Manages time, event scheduling, and agent registration for discrete event simulations.
    
    Args:
        real_time: Enable real-time simulation (default: False)
        current_time: Initialize with current system time (default: False)
    """
    def __init__(self, real_time: Union[float,int,bool] = False, current_time: bool = False):
        sim.Environment.__init__(self)
        self._now = 0.0 if not current_time else time.time()
        self.scheduler = Scheduler(self._time, self._sleep, self)
        self._objects = list()
        self._agents = OrderedDict()
        self.counter = Counter()
        self._debug = DEBUG
    
    def add_agent(self, obj: Any) -> None:
        """Add an agent to the environment's agent registry."""
        count = self.counter()
        key = obj.name if obj.name is not None else count
        self._agents[key] = obj
        
    def _activate_fsm(self) -> None:
        """Activate finite state machines for all registered agents."""
        for ag in self._agents.values():
            ag.activate_fsm()

    @property
    def now(self) -> float:
        """Get the current simulation time."""
        return self._time()

    def schedule(self, delay: float, priority: int, action: Callable[..., Any], *args: Any, **kwargs: Any) -> Event:
        """
        Schedule an event with a relative delay.
        
        Args:
            delay: Time delay from current time
            priority: Event priority (lower values execute first)
            action: Callable to execute when event fires
            *args: Positional arguments for action
            **kwargs: Keyword arguments for action
            
        Returns:
            The scheduled event
        """
        return self.scheduler.delay(delay, priority, action, args, kwargs)

    def schedule_absolute(self, time: float, priority: int, action: Callable[..., Any], *args: Any, **kwargs: Any) -> Event:
        """
        Schedule an event at an absolute simulation time.
        
        Args:
            time: Absolute simulation time for event
            priority: Event priority (lower values execute first)
            action: Callable to execute when event fires
            *args: Positional arguments for action
            **kwargs: Keyword arguments for action
            
        Returns:
            The scheduled event
        """
        return self.scheduler.enterabs(time, priority, action, args, kwargs)

    def run(self, until: Optional[float] = None) -> None:
        """
        Run the simulation.
        
        Args:
            until: Stop time (if None, runs until event queue is empty)
        """
        self._activate_fsm()
        if until is not None:
            if until < self.now:
                until += self.now
            self.scheduler.enterabs(until, 0, kwargs={"StopSimulation": True})
        self.scheduler.run(blocking=True)

    def _stop_simulation(self) -> None:
        """Stop the simulation by clearing the event queue."""
        self.scheduler.queue.clear()

class RealTimeEnvironment(BaseEnvironment):
    """
    Real-time simulation environment.
    
    Time advances based on actual wall-clock time, scaled by real_time factor.
    
    Args:
        real_time: Time scaling factor (default: 1.0). 
                   real_time=2 means simulation runs twice as fast as real time.
        current_time: Initialize with current system time (default: False)
    """
    def __init__(self, real_time: Union[float,int] = 1, current_time: bool = False):
        super().__init__(current_time=current_time)
        self._real_time = real_time if real_time is not True else 1.0
        
    def _time(self) -> float:
        """Get current wall-clock time."""
        return time.time()

    def _sleep(self, delay: float) -> None:
        """Sleep for scaled delay duration."""
        time.sleep(delay/self._real_time)

        
class Environment(BaseEnvironment):
    """
    Virtual time simulation environment.
    
    Time advances only when events are processed. No wall-clock delays.
    This is the standard discrete event simulation environment.
    
    Args:
        current_time: Initialize with current system time (default: False)
    """
    def __init__(self, current_time: bool = False):
        super().__init__(current_time=current_time)
    
    @property
    def now(self) -> float:
        """Get current virtual simulation time."""
        return self._now
        
    def _time(self) -> float:
        """Get current virtual simulation time."""
        return self._now

    def _sleep(self, delay: float) -> None:
        """Advance virtual time by delay amount."""
        self._now += delay