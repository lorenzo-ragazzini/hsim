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

    
from sortedcontainers import SortedList
from heapq import heappush as push, heappop as pop
import time
from typing import Any, Callable, Optional, Union
from collections import OrderedDict

import numpy as np
from hsim.core.core.event import BaseEvent as Event, Status
from hsim.core.core.event import TimedEvent

# Recorder import (moved to top)
try:
    from hsim.core.debug.sequence_recorder import get_recorder
except Exception:
    def get_recorder():
        class _Dummy:
            def record_message_send(self, *a, **k): pass
            def record_message_received(self, *a, **k): pass
            def record_message_read(self, *a, **k): pass
            def record_event_trigger(self, *a, **k): pass
            def record_event_execute(self, *a, **k): pass
        return _Dummy()

DEBUG = False



class Scheduler():
    def __init__(self, timefunc: Callable[[], float], delayfunc: Callable[[float], None], env:'Environment'):
        self._lock = Context()
        self._past = list()
        self._env = env
        self._queue = [] #SortedList(key=lambda event: (event.time, event.priority, -event.sequence))
        class Never(dict):
            def add(self, event):
                super().update({id(event): event})
            def remove(self, event):
                return super().pop(id(event), None)
        self._never = Never()
        # self._conditions = SortedList(key=lambda event: (event.time, event.priority, event.sequence))
        self._sequence_generator = Counter()
        self.timefunc = timefunc
        self.delayfunc = delayfunc
    def enter(self, event: 'Event') -> 'Event':
        # self._queue.add(event)
        # event._in_queue = True
        if event.time == np.inf:
            self._never.add(event)
        else:
            push(self._queue, event)
            event._in_queue = True
        return event
    def enterabs(self, time, priority, action=object, argument=(), kwargs={}) -> 'Event':
        return self.enter(TimedEvent(self._env, time, priority, action, argument, **kwargs))
    def delay(self, delay, priority, action=object, argument=(), kwargs={}) -> 'Event':
        return self.enterabs(self.timefunc() + delay, priority, action, argument, kwargs)
    def late(self, priority, action, argument=(), kwargs={}):
        return self.enterabs(np.inf, priority, action, argument, kwargs)
    def run(self, blocking=True):
        delayfunc, timefunc, lock, past = self.delayfunc, self.timefunc, self._lock, self._past
        while self._queue:
            event = pop(self._queue)
            event._in_queue = False
            if len(self._queue) < 3:
                pass
            if getattr(event, "_canceled", False):
                continue
            elif event.time == np.inf:
                raise RuntimeError(f"Event {event} has infinite time but is still in the queue. This should not happen. Event should  have been canceled")
            delayfunc(event.time - timefunc())
            if event.pending:
                raise RuntimeError(f"Event {event} is still pending after delay. This should not happen.")
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
            # Only check conditioned events in the queue
            # self.check_conditioned_events()
    # def check_conditioned_events(self):
    #     for cond_event in self._conditions:
    #         if not getattr(cond_event, "_canceled", False) and cond_event.verify():
    #             break
    def execute(self,event):
        """
        Execute event action(s).
        
        Args:
            event: Event to execute
        """
        # Record execution using recorder
        try:
            get_recorder().record_event_execute(event)
        except Exception:
            pass

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
    # def cancel(self, event):
    #     print(f"Canceling event: {event}")
    #     # Just flag as canceled, do not remove from queue
    #     event.cancel()

    # def cleaner(self):
    #     # Remove all canceled events from the queue
    #     canceled_events = [e for e in self._queue if getattr(e, "_canceled", False)]
    #     for event in canceled_events:
    #         event._in_queue = False
    #     self._queue = type(self._queue)([e for e in self._queue if not getattr(e, "_canceled", False)], key=self._queue.key)
    #     self._conditions = type(self._conditions)([e for e in self._conditions if not getattr(e, "_canceled", False)], key=self._conditions.key)
        
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
    
class BaseEnvironment:
    """
    Base class for simulation environments.
    
    Manages time, event scheduling, and agent registration for discrete event simulations.
    
    Args:
        real_time: Enable real-time simulation (default: False)
        current_time: Initialize with current system time (default: False)
    """
    def __init__(self, real_time: Union[float,int,bool] = False, current_time: bool = False):
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
        return self.scheduler.enter(delay, priority, action, args, kwargs)

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