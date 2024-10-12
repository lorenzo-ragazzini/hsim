import heapq
import sched
import threading
import time
from typing import Any, Callable, Optional, Union
from collections import deque

import numpy as np
from event import BaseEvent as Event, Status
from event import TimedEvent


class Scheduler(sched.scheduler):
    def __init__(self, timefunc: Callable[[], float], delayfunc: Callable[[float], None], env:'Environment'):
        super().__init__(timefunc, delayfunc)
        self._lock = Context()
        self._past = list()
        self._env = env
    def heapify(self):
        heapq.heapify(self._queue)
    def enter(self, event: 'Event') -> 'Event':
        heapq.heappush(self._queue, event)
        heapq.heapify(self._queue)
        return event
    def enterabs(self, time, priority, action=object, argument=(), kwargs=sched._sentinel) -> 'Event':
        if kwargs is sched._sentinel:
            kwargs = {}
        return self.enter(TimedEvent(self._env, time, priority, action, argument, **kwargs))
    def delay(self, delay, priority, action=object, argument=(), kwargs=sched._sentinel) -> 'Event':
        return self.enterabs(self.timefunc() + delay, priority, action, argument, kwargs)
    def late(self, priority, action, argument=(), kwargs=sched._sentinel):
        return self.enterabs(np.inf, priority, action, argument, kwargs)
    def run(self, blocking=True):
        delayfunc, timefunc, pop, push, lock, past = self.delayfunc, self.timefunc, heapq.heappop, heapq.heappush, self._lock, self._past
        while True:
            with lock:
                if not self.queue:
                    break
                event = self.queue[0]
                now = timefunc()
                if event.time > now:
                    delay = True
                else:
                    delay = False
                    pop(self.queue), pop(self._queue)
            if delay:
                delayfunc(event.time - now)
            else:
                if event.pending:
                    event.time = np.inf
                    event.schedule()
                    self.enterevent(event)
                elif "StopSimulation" in event.kwargs:
                    break
                else:
                    event.trigger()
                    if callable(event.action):
                        event.action(*event.arguments, **event.kwargs)
                    else: #Iterable
                        if len(event.arguments) == 0:
                            event.arguments = [() for _ in range(len(event.action))]
                        elif len(event.arguments) != len(event.action):
                            raise ValueError("Arguments do not match")
                        for index, action in enumerate(event.action):
                            action(*event.arguments[index], **event.kwargs)
                    delayfunc(0)   # Let other threads run
                    push(self._past, event)
                    event.process()
        '''
        while True:
            if not self.queue:
                break
            event = self.queue[0]
            now = timefunc()
            if event.time > now:
                delay = True
            else:
                delay = False
                event, _ = pop(self.queue), pop(self._queue)
            if delay:
                if not blocking:
                    return event.time - now
                delayfunc(event.time - now)
            elif event.pending:
                event.time = np.inf
                event.schedule()
                self.enterevent(event)
            else:
                if event.scheduled:
                    event.trigger()
                elif "StopSimulation" in event.kwargs:
                    break
                elif event.triggered:
                    push(self._past, event)
                    event.action(*event.arguments)
                    # event.action(*argument, **kwargs)
                    delayfunc(0)   # Let other threads run
                    event.process()
                else:
                    raise ValueError("Undefined event status")'''
    @property
    def queue(self):
        events = [event for event in self._queue if event.time >= self.timefunc() and event.time < float('inf')]
        return list(map(heapq.heappop, [events]*len(events)))
    def cancel(self, event):
        self._queue.remove(event)
        heapq.heapify(self._queue)
        
class Context:
    def __enter__(self):
        pass
    def __exit__(self,a,b,c):
        pass
    
class Environment:
    def __init__(self, real_time: Union[float,int,bool] = False, current_time: bool = False):
        self._now = 0.0 if not current_time else time.time()
        self._real_time = real_time if real_time is not True else 1.0
        self.scheduler = Scheduler(self._time, self._sleep, self)
        self._objects = list()

    def _time(self) -> float:
        return time.time() if self._real_time else self._now

    def _sleep(self, delay: float) -> None:
        if self._real_time:
            time.sleep(delay/self._real_time)
        else:
            self._now += delay

    @property
    def now(self) -> float:
        return self._time()

    def schedule(self, delay: float, priority: int, action: Callable[..., Any], *args: Any, **kwargs: Any) -> sched.Event:
        return self.scheduler.enter(delay, priority, action, args, kwargs)

    def schedule_absolute(self, time: float, priority: int, action: Callable[..., Any], *args: Any, **kwargs: Any) -> sched.Event:
        return self.scheduler.enterabs(time, priority, action, args, kwargs)

    def run(self, until: Optional[float] = None) -> None:
        if until is not None:
            if until < self.now:
                until += self.now
            self.scheduler.enterabs(until, 0, kwargs={"StopSimulation": True})
        self.scheduler.run(blocking=True)

    def _stop_simulation(self) -> None:
        self.scheduler.queue.clear()

# Circular import to resolve type hinting
