"""Integration tests: CompatScheduler / HSimEnvironment backed by salabim."""
import pytest
import numpy as np

def make_env():
    from hsim.core.core.env import Environment
    return Environment()

class TestInit:
    def test_now_zero(self):
        assert make_env().now == 0.0

    def test_compat_scheduler(self):
        from hsim.core.core.env import CompatScheduler
        assert isinstance(make_env().scheduler, CompatScheduler)

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

class TestPriority:
    def test_lower_priority_fires_first(self):
        from hsim.core.core.event import TimedEvent
        env = make_env()
        order = []
        TimedEvent(env, time=5, priority=2, action=lambda: order.append("low")).add()
        TimedEvent(env, time=5, priority=1, action=lambda: order.append("high")).add()
        env.run(until=10)
        assert order == ["high", "low"]
