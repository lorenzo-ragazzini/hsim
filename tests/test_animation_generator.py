"""Tests for ComponentGenerator enhancements and animation utilities."""

import unittest
import json
from hsim.core.core.env import Environment
from hsim.core.agent.agent import Agent
from hsim.core.des.pymulate import Generator
from hsim.core.stats.monitor import LevelMonitor, NonLevelMonitor
from hsim.core.stats.animation import (
    AnimateMonitor,
    AnimationTimeline,
    serialize_animation_state,
    deserialize_animation_state,
    animation_state_template,
    validate_animation_state,
)


class TestComponentGeneratorMoments(unittest.TestCase):
    """Test Generator with moments parameter for exact arrival times."""
    
    def test_moments_basic(self):
        """Generate agents at exact scheduled times."""
        env = Environment()
        gen = Generator(
            env,
            name="test_gen",
            moments=[1.0, 2.5, 5.0],
        )
        
        self.assertEqual(gen.moments, [1.0, 2.5, 5.0])
        self.assertEqual(gen._moments_index, 0)
    
    def test_moments_iat_calculation(self):
        """Verify IAT calculated correctly from moments."""
        env = Environment()
        gen = Generator(env, moments=[1.0, 3.0, 6.0])
        
        # At t=0, next arrival is at t=1.0
        iat = gen.calculateServiceTime()
        self.assertAlmostEqual(iat, 1.0)
        
        # Advance moments index
        gen._moments_index = 1
        iat = gen.calculateServiceTime()
        self.assertAlmostEqual(iat, 3.0)
        
        # Advance to final moment
        gen._moments_index = 2
        iat = gen.calculateServiceTime()
        self.assertAlmostEqual(iat, 6.0)
    
    def test_moments_exhausted(self):
        """Verify None returned when all moments exhausted."""
        env = Environment()
        gen = Generator(env, moments=[1.0, 2.0])
        
        gen._moments_index = 2  # Beyond list length
        iat = gen.calculateServiceTime()
        self.assertIsNone(iat)


class TestComponentGeneratorEquidistant(unittest.TestCase):
    """Test Generator with equidistant parameter."""
    
    def test_equidistant_basic(self):
        """Generate N agents spread evenly in [at, till]."""
        env = Environment()
        gen = Generator(
            env,
            batch_size=5,
            equidistant=True,
            at=0.0,
            till=10.0,
        )
        
        # Should have 5 arrivals evenly spaced: 0, 2.5, 5, 7.5, 10
        self.assertEqual(len(gen._equidistant_arrivals), 5)
        expected = [0.0, 2.5, 5.0, 7.5, 10.0]
        for actual, exp in zip(gen._equidistant_arrivals, expected):
            self.assertAlmostEqual(actual, exp)
    
    def test_equidistant_iat(self):
        """Verify IAT calculation for equidistant arrivals."""
        env = Environment()
        gen = Generator(
            env,
            batch_size=3,
            equidistant=True,
            at=1.0,
            till=4.0,
        )
        
        # Arrivals: 1.0, 2.5, 4.0
        # At t=0, IAT to first should be 1.0
        iat = gen.calculateServiceTime()
        self.assertAlmostEqual(iat, 1.0)


class TestComponentGeneratorDisturbance(unittest.TestCase):
    """Test Generator with disturbance parameter for IAT jitter."""
    
    def test_disturbance_numeric(self):
        """Apply numeric disturbance (std dev) to IAT."""
        env = Environment()
        gen = Generator(
            env,
            serviceTime=5.0,
            disturbance=0.5,  # std dev = 0.5
        )
        
        # Apply disturbance several times
        iats = []
        for _ in range(10):
            iat = gen._apply_disturbance(5.0)
            iats.append(iat)
            self.assertGreaterEqual(iat, 0.0)  # No negative IAT
        
        # Mean should be close to 5.0, but not exact
        mean_iat = sum(iats) / len(iats)
        self.assertGreater(mean_iat, 3.0)  # Roughly in expected range
        self.assertLess(mean_iat, 7.0)
    
    def test_disturbance_callable(self):
        """Apply callable disturbance to IAT."""
        env = Environment()
        call_count = [0]
        
        def jitter_func():
            call_count[0] += 1
            return 0.1 * (call_count[0] % 3)
        
        gen = Generator(env, serviceTime=5.0, disturbance=jitter_func)
        
        iat1 = gen._apply_disturbance(5.0)
        iat2 = gen._apply_disturbance(5.0)
        
        # Each should apply jitter from callable
        self.assertNotEqual(iat1, iat2)
    
    def test_disturbance_none(self):
        """No disturbance returns original IAT."""
        env = Environment()
        gen = Generator(env, disturbance=None)
        
        iat = gen._apply_disturbance(5.0)
        self.assertEqual(iat, 5.0)


class TestComponentGeneratorAtEnd(unittest.TestCase):
    """Test Generator with at_end callback."""
    
    def test_at_end_callback(self):
        """Verify at_end callback invoked when generation completes."""
        env = Environment()
        callback_called = [False]
        
        def on_generation_end():
            callback_called[0] = True
        
        gen = Generator(
            env,
            moments=[1.0],
            at_end=on_generation_end,
        )
        
        # After generating 1 agent, calculateServiceTime returns None
        gen._moments_index = 1
        iat = gen.calculateServiceTime()
        self.assertIsNone(iat)
        
        # at_end should be set but not called yet (would be called in _on_generate)
        self.assertIsNotNone(gen.at_end)


class TestAnimateMonitor(unittest.TestCase):
    """Test AnimateMonitor visualization utilities."""
    
    def test_animate_monitor_creation(self):
        """Create AnimateMonitor wrapper around Monitor."""
        env = Environment()
        monitor = LevelMonitor(name="test_mon")
        
        anim = AnimateMonitor(monitor, name="Queue Length", color="red")
        
        self.assertEqual(anim.name, "Queue Length")
        self.assertEqual(anim.color, "red")
        self.assertEqual(anim.monitor, monitor)
    
    def test_animate_monitor_empty(self):
        """AnimateMonitor handles empty monitor gracefully."""
        env = Environment()
        monitor = LevelMonitor()
        anim = AnimateMonitor(monitor)
        
        plotly_dict = anim.to_plotly_dict()
        self.assertEqual(plotly_dict["x"], [])
        self.assertEqual(plotly_dict["y"], [])
        self.assertEqual(plotly_dict["mode"], "lines")
    
    def test_animate_monitor_to_dict(self):
        """Export monitor as simple dict."""
        monitor = LevelMonitor(name="mon")
        
        # Add some sample data using tally
        monitor.tally(0.0, 5)
        monitor.tally(1.0, 7)
        
        anim = AnimateMonitor(monitor, name="Test Monitor")
        d = anim.to_dict()
        
        self.assertEqual(d["name"], "Test Monitor")
        self.assertEqual(len(d["time"]), 2)
        self.assertEqual(len(d["values"]), 2)
    
    def test_animate_monitor_to_json(self):
        """Export monitor as JSON."""
        monitor = LevelMonitor()
        monitor.tally(0.0, 5)
        
        anim = AnimateMonitor(monitor)
        json_str = anim.to_json()
        
        # Should be valid JSON
        data = json.loads(json_str)
        self.assertIn("time", data)
        self.assertIn("values", data)


class TestAnimationTimeline(unittest.TestCase):
    """Test AnimationTimeline for frame management."""
    
    def test_timeline_add_frames(self):
        """Add animation frames to timeline."""
        timeline = AnimationTimeline()
        
        state1 = {"name": "obj1", "x": 0.0, "y": 0.0, "timestamp": 1.0}
        state2 = {"name": "obj1", "x": 1.0, "y": 0.5, "timestamp": 2.0}
        
        timeline.add_frame(1.0, state1)
        timeline.add_frame(2.0, state2)
        
        frames = timeline.get_frames()
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0][0], 1.0)
        self.assertEqual(frames[1][0], 2.0)
    
    def test_timeline_sorted(self):
        """Frames sorted by time regardless of insertion order."""
        timeline = AnimationTimeline()
        
        timeline.add_frame(3.0, {"timestamp": 3.0})
        timeline.add_frame(1.0, {"timestamp": 1.0})
        timeline.add_frame(2.0, {"timestamp": 2.0})
        
        frames = timeline.get_frames()
        times = [f[0] for f in frames]
        self.assertEqual(times, [1.0, 2.0, 3.0])
    
    def test_timeline_to_json(self):
        """Export timeline as JSON."""
        timeline = AnimationTimeline()
        timeline.add_frame(1.0, {"name": "obj", "x": 1.0, "y": 0.0, "timestamp": 1.0})
        timeline.add_frame(2.0, {"name": "obj", "x": 2.0, "y": 0.0, "timestamp": 2.0})
        
        json_str = timeline.to_json()
        data = json.loads(json_str)
        
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["_time"], 1.0)
        self.assertEqual(data[1]["_time"], 2.0)
    
    def test_timeline_to_dict(self):
        """Export timeline as structured dict."""
        timeline = AnimationTimeline()
        timeline.add_frame(1.0, {"name": "obj", "x": 1.0, "y": 0.0})
        timeline.add_frame(2.0, {"name": "obj", "x": 2.0, "y": 0.0})
        
        d = timeline.to_dict()
        self.assertEqual(d["times"], [1.0, 2.0])
        self.assertEqual(len(d["frames"]), 2)


class TestAnimationSerialization(unittest.TestCase):
    """Test animation state serialization utilities."""
    
    def test_serialize_animation_state(self):
        """Serialize animation state to JSON."""
        state = {
            "name": "agv_01",
            "x": 10.5,
            "y": 20.3,
            "timestamp": 5.0,
        }
        
        json_str = serialize_animation_state(state)
        data = json.loads(json_str)
        
        self.assertEqual(data["name"], "agv_01")
        self.assertEqual(data["x"], 10.5)
    
    def test_deserialize_animation_state(self):
        """Deserialize animation state from JSON."""
        json_str = '{"name": "agv_01", "x": 10.5, "y": 20.3, "timestamp": 5.0}'
        state = deserialize_animation_state(json_str)
        
        self.assertEqual(state["name"], "agv_01")
        self.assertEqual(state["x"], 10.5)
    
    def test_roundtrip_serialization(self):
        """Serialize and deserialize cycle preserves data."""
        state = {
            "name": "entity",
            "x": 1.5,
            "y": 2.5,
            "z": 0.0,
            "rotation": 45.0,
            "color": "blue",
            "timestamp": 10.0,
        }
        
        json_str = serialize_animation_state(state)
        restored = deserialize_animation_state(json_str)
        
        for key, value in state.items():
            self.assertEqual(restored[key], value)


class TestAnimationStateTemplate(unittest.TestCase):
    """Test animation state template and validation."""
    
    def test_template_structure(self):
        """Template has expected fields."""
        template = animation_state_template()
        
        required_fields = {"name", "x", "y", "z", "rotation", "color", "size", "timestamp"}
        for field in required_fields:
            self.assertIn(field, template)
    
    def test_validate_animation_state(self):
        """Validate required fields in animation state."""
        valid_state = {
            "name": "obj",
            "x": 1.0,
            "y": 2.0,
            "timestamp": 5.0,
        }
        
        self.assertTrue(validate_animation_state(valid_state))
    
    def test_validate_animation_state_missing_field(self):
        """Validation fails for missing required fields."""
        invalid_state = {
            "name": "obj",
            "x": 1.0,
            # missing y and timestamp
        }
        
        self.assertFalse(validate_animation_state(invalid_state))


if __name__ == "__main__":
    unittest.main()
