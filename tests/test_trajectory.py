"""Tests for Trajectory classes."""

import unittest
import math
from hsim.core.des.trajectory import (
    TrajectoryPolygon,
    TrajectoryCircle,
    TrajectoryMerged,
    AnimationState,
    TrajectoryFollower,
    _Movement
)


class TestMovement(unittest.TestCase):
    """Test _Movement segment class."""
    
    def test_horizontal_movement(self):
        """Test movement along x-axis."""
        mov = _Movement(0, 0, 10, 0, vmax=2.0)
        
        self.assertAlmostEqual(mov.distance, 10.0)
        self.assertAlmostEqual(mov.duration, 5.0)
        
        # At t=0, should be at start
        x, y = mov.position(0)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)
        
        # At midpoint (t=2.5)
        x, y = mov.position(2.5)
        self.assertAlmostEqual(x, 5.0)
        self.assertAlmostEqual(y, 0)
        
        # Beyond end
        x, y = mov.position(10.0)
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 0)
    
    def test_diagonal_movement(self):
        """Test movement along diagonal."""
        mov = _Movement(0, 0, 3, 4, vmax=5.0)
        
        # Distance = sqrt(9 + 16) = 5
        self.assertAlmostEqual(mov.distance, 5.0)
        self.assertAlmostEqual(mov.duration, 1.0)
        
        # At end
        x, y = mov.position(1.0)
        self.assertAlmostEqual(x, 3.0)
        self.assertAlmostEqual(y, 4.0)
    
    def test_velocity(self):
        """Test velocity vector."""
        mov = _Movement(0, 0, 10, 0, vmax=2.0)
        vx, vy = mov.velocity()
        
        self.assertAlmostEqual(vx, 2.0)
        self.assertAlmostEqual(vy, 0)


class TestTrajectoryPolygon(unittest.TestCase):
    """Test TrajectoryPolygon class."""
    
    def test_simple_square(self):
        """Test square trajectory."""
        polygon = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        traj = TrajectoryPolygon(polygon, vmax=10.0)
        
        # Total distance = 40, vmax=10 => duration = 4
        self.assertAlmostEqual(traj.duration, 4.0)
        
        # At start
        x, y = traj.position(0)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)
        
        # At t=1 (10 units down, at corner 1)
        x, y = traj.position(1.0)
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 0)
        
        # At t=2 (10 units up, at corner 2)
        x, y = traj.position(2.0)
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 10.0)
        
        # At end
        x, y = traj.position(4.0)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)
    
    def test_x_y_accessors(self):
        """Test individual x and y accessors."""
        polygon = [(0, 0), (5, 0), (5, 3)]
        traj = TrajectoryPolygon(polygon, vmax=1.0)
        
        # First segment: horizontal
        self.assertAlmostEqual(traj.x(0), 0)
        self.assertAlmostEqual(traj.y(0), 0)
        
        self.assertAlmostEqual(traj.x(2.5), 2.5)
        self.assertAlmostEqual(traj.y(2.5), 0)
        
        # Second segment: vertical
        self.assertAlmostEqual(traj.x(5), 5.0)
        self.assertAlmostEqual(traj.y(5), 0)
        
        self.assertAlmostEqual(traj.x(7), 5.0)
        self.assertAlmostEqual(traj.y(7), 2.0)
    
    def test_segments_property(self):
        """Test segments count."""
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        traj = TrajectoryPolygon(polygon, vmax=1.0)
        
        self.assertEqual(traj.segments(), 3)


class TestTrajectoryCircle(unittest.TestCase):
    """Test TrajectoryCircle class."""
    
    def test_quarter_circle(self):
        """Test quarter circle (0 to 90 degrees)."""
        # Circle at origin with radius 1, quarter circle
        traj = TrajectoryCircle(
            center=(0, 0),
            radius=1.0,
            vmax=math.pi / 2,  # Quarter circle length
            angle_start=0,
            angle_end=90
        )
        
        # Arc length = (90/360) * 2π * 1 = π/2
        expected_duration = (math.pi / 2) / (math.pi / 2)
        self.assertAlmostEqual(traj.duration, expected_duration)
        
        # At start (0 degrees = right)
        x, y = traj.position(0)
        self.assertAlmostEqual(x, 1.0, places=5)
        self.assertAlmostEqual(y, 0.0, places=5)
        
        # At midpoint (45 degrees)
        t_mid = traj.duration / 2
        x, y = traj.position(t_mid)
        expected_x = math.cos(math.radians(45))
        expected_y = math.sin(math.radians(45))
        self.assertAlmostEqual(x, expected_x, places=5)
        self.assertAlmostEqual(y, expected_y, places=5)
        
        # At end (90 degrees = up)
        x, y = traj.position(traj.duration)
        self.assertAlmostEqual(x, 0.0, places=5)
        self.assertAlmostEqual(y, 1.0, places=5)
    
    def test_full_circle(self):
        """Test full circle trajectory."""
        traj = TrajectoryCircle(
            center=(5, 5),
            radius=2.0,
            vmax=math.pi,  # Arc length
            angle_start=0,
            angle_end=360
        )
        
        # Arc length = 2π * 2 = 4π
        expected_duration = (4 * math.pi) / math.pi
        self.assertAlmostEqual(traj.duration, expected_duration)
        
        # Start and end should be same point
        x1, y1 = traj.position(0)
        x2, y2 = traj.position(traj.duration)
        self.assertAlmostEqual(x1, x2, places=5)
        self.assertAlmostEqual(y1, y2, places=5)


class TestTrajectoryMerged(unittest.TestCase):
    """Test TrajectoryMerged class."""
    
    def test_two_segments(self):
        """Test merging two simple line segments."""
        # Line from (0,0) to (5,0)
        line1 = TrajectoryPolygon([(0, 0), (5, 0)], vmax=5.0)
        # Line from (5,0) to (5,5)
        line2 = TrajectoryPolygon([(5, 0), (5, 5)], vmax=5.0)
        
        merged = TrajectoryMerged([line1, line2])
        
        # Total duration should be 1 + 1 = 2
        self.assertAlmostEqual(merged.duration, 2.0)
        
        # At start, should be at beginning of first
        x, y = merged.position(0)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)
        
        # At t=1, should be at junction
        x, y = merged.position(1.0)
        self.assertAlmostEqual(x, 5.0)
        self.assertAlmostEqual(y, 0)
        
        # At t=2, should be at end of second
        x, y = merged.position(2.0)
        self.assertAlmostEqual(x, 5.0)
        self.assertAlmostEqual(y, 5.0)
    
    def test_segments_property(self):
        """Test segments count."""
        line1 = TrajectoryPolygon([(0, 0), (1, 0)], vmax=1.0)
        line2 = TrajectoryPolygon([(1, 0), (1, 1)], vmax=1.0)
        merged = TrajectoryMerged([line1, line2])
        
        self.assertEqual(merged.segments(), 2)


class TestAnimationState(unittest.TestCase):
    """Test AnimationState serialization."""
    
    def test_animation_state_dict(self):
        """Test conversion to dictionary."""
        state = AnimationState(
            name="agv_01",
            x=5.0,
            y=10.0,
            z=0.5,
            rotation=45.0,
            color="red",
            size=2.0
        )
        
        d = state.to_dict()
        
        self.assertEqual(d["name"], "agv_01")
        self.assertEqual(d["x"], 5.0)
        self.assertEqual(d["y"], 10.0)
        self.assertEqual(d["z"], 0.5)
        self.assertEqual(d["rotation"], 45.0)
        self.assertEqual(d["color"], "red")
        self.assertEqual(d["size"], 2.0)


class TestTrajectoryFollower(unittest.TestCase):
    """Test TrajectoryFollower mixin."""
    
    def test_follower_position(self):
        """Test getting position from follower."""
        trajectory = TrajectoryPolygon([(0, 0), (10, 0)], vmax=10.0)
        
        class Agent(TrajectoryFollower):
            def __init__(self, traj):
                super().__init__(traj)
        
        agent = Agent(trajectory)
        agent.start_trajectory(at_time=0)
        
        # At t=0
        x, y = agent.get_position(0)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)
        
        # At t=0.5
        x, y = agent.get_position(0.5)
        self.assertAlmostEqual(x, 5.0)
        self.assertAlmostEqual(y, 0)
        
        # At t=1 (end)
        x, y = agent.get_position(1.0)
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 0)
    
    def test_follower_delayed_start(self):
        """Test trajectory starting at non-zero time."""
        trajectory = TrajectoryPolygon([(0, 0), (10, 0)], vmax=10.0)
        
        class Agent(TrajectoryFollower):
            def __init__(self, traj):
                super().__init__(traj)
        
        agent = Agent(trajectory)
        agent.start_trajectory(at_time=100)
        
        # At t=100 (start)
        x, y = agent.get_position(100)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 0)
        
        # At t=100.5
        x, y = agent.get_position(100.5)
        self.assertAlmostEqual(x, 5.0)
        self.assertAlmostEqual(y, 0)
    
    def test_animation_state_generation(self):
        """Test animation state from follower."""
        trajectory = TrajectoryPolygon([(0, 0), (10, 0)], vmax=10.0)
        
        class Agent(TrajectoryFollower):
            def __init__(self, traj):
                super().__init__(traj)
        
        agent = Agent(trajectory)
        agent.start_trajectory(at_time=0)
        
        state = agent.animation_state(0.5, name="agv_1", color="blue")
        
        self.assertEqual(state.name, "agv_1")
        self.assertEqual(state.color, "blue")
        self.assertAlmostEqual(state.x, 5.0)
        self.assertAlmostEqual(state.y, 0)


if __name__ == "__main__":
    unittest.main()
