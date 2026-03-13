"""Integration tests that visualize Monitor, Resource, and Animation data."""

import unittest
import json
from pathlib import Path
from hsim.core.core.env import Environment
from hsim.core.stats.monitor import LevelMonitor, NonLevelMonitor
from hsim.core.des.resources import Resource
from hsim.core.des.trajectory import (
    TrajectoryPolygon, TrajectoryCircle, TrajectoryMerged,
    TrajectoryFollower, AnimationState
)
from hsim.core.stats.animation import AnimateMonitor, AnimationTimeline
from tests.test_visualization import (
    visualize_monitor_html,
    visualize_resource_html,
    visualize_trajectory_html,
    visualize_animation_timeline_html,
    print_visualization_summary,
)


class TestMonitorVisualization(unittest.TestCase):
    """Test Monitor visualization and export."""
    
    def test_level_monitor_visualization(self):
        """Visualize LevelMonitor time-series data."""
        monitor = LevelMonitor(name="Queue Length")
        
        # Simulate queue length changes
        monitor.tally(0.0, 0)
        monitor.tally(1.5, 3)
        monitor.tally(2.0, 5)
        monitor.tally(3.5, 4)
        monitor.tally(5.0, 1)
        monitor.tally(6.0, 0)
        
        # Generate visualization
        output_path = "/tmp/level_monitor_viz.html"
        result_path = visualize_monitor_html(monitor, "Queue Length Over Time", output_path)
        
        # Verify file created
        self.assertTrue(Path(result_path).exists())
        
        # Verify HTML contains plot data
        with open(result_path, 'r') as f:
            html = f.read()
            self.assertIn("plotly", html.lower())
            self.assertIn("Queue Length", html)
    
    def test_non_level_monitor_visualization(self):
        """Visualize NonLevelMonitor discrete samples."""
        monitor = NonLevelMonitor(name="Service Time")
        
        # Record sample service times
        samples = [2.1, 2.3, 1.9, 2.5, 2.2, 2.4, 1.8, 2.6]
        for sample in samples:
            monitor.tally(sample)
        
        # Generate visualization
        output_path = "/tmp/non_level_monitor_viz.html"
        result_path = visualize_monitor_html(monitor, "Service Time Samples", output_path)
        
        # Verify file created and contains expected data
        self.assertTrue(Path(result_path).exists())
        with open(result_path, 'r') as f:
            html = f.read()
            self.assertIn("Service Time", html)
    
    def test_monitor_json_export(self):
        """Export Monitor data as JSON."""
        monitor = LevelMonitor(name="Utilization")
        
        monitor.tally(0.0, 0.5)
        monitor.tally(10.0, 0.8)
        monitor.tally(20.0, 0.6)
        
        # Export via AnimateMonitor
        anim = AnimateMonitor(monitor, name="Utilization")
        json_str = anim.to_json()
        
        # Verify valid JSON
        data = json.loads(json_str)
        self.assertIn("time", data)
        self.assertIn("values", data)
        self.assertEqual(len(data["time"]), 3)


class TestResourceVisualization(unittest.TestCase):
    """Test Resource occupancy visualization."""
    
    def test_resource_visualization(self):
        """Visualize Resource capacity, available, claimed, occupancy."""
        env = Environment()
        resource = Resource("Machine", capacity=5, env=env)
        
        # Simulate request/release pattern
        class MockAgent:
            def __init__(self, name):
                self.name = name
        
        agent1 = MockAgent("Agent1")
        agent2 = MockAgent("Agent2")
        
        # Request sequence
        resource.request(agent1, 2)  # Agent1 claims 2
        resource.capacity_monitor.tally(env.now, resource.capacity)
        resource.available_monitor.tally(env.now, resource._available)
        resource.claimed_monitor.tally(env.now, resource._claimed)
        resource.occupancy_monitor.tally(env.now, len(resource._queue))
        
        resource.request(agent2, 2)  # Agent2 claims 2
        resource.capacity_monitor.tally(env.now, resource.capacity)
        resource.available_monitor.tally(env.now, resource._available)
        resource.claimed_monitor.tally(env.now, resource._claimed)
        resource.occupancy_monitor.tally(env.now, len(resource._queue))
        
        resource.release(agent1, 2)  # Agent1 releases 2
        resource.capacity_monitor.tally(env.now, resource.capacity)
        resource.available_monitor.tally(env.now, resource._available)
        resource.claimed_monitor.tally(env.now, resource._claimed)
        resource.occupancy_monitor.tally(env.now, len(resource._queue))
        
        # Generate visualization
        output_path = "/tmp/resource_viz.html"
        result_path = visualize_resource_html(resource, output_path)
        
        # Verify file created
        self.assertTrue(Path(result_path).exists())
        with open(result_path, 'r') as f:
            html = f.read()
            self.assertIn("Resource", html)
            self.assertIn("Capacity", html)
            self.assertIn("Available", html)


class TestTrajectoryVisualization(unittest.TestCase):
    """Test Trajectory path visualization."""
    
    def test_polygon_trajectory_visualization(self):
        """Visualize polygonal trajectory path."""
        # Square path
        polygon = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        traj = TrajectoryPolygon(polygon, vmax=5.0)
        
        # Generate visualization
        output_path = "/tmp/polygon_trajectory_viz.html"
        result_path = visualize_trajectory_html(traj, "Square Path", output_path)
        
        # Verify file created
        self.assertTrue(Path(result_path).exists())
        with open(result_path, 'r') as f:
            html = f.read()
            self.assertIn("Square Path", html)
            self.assertIn("plot", html.lower())
    
    def test_circle_trajectory_visualization(self):
        """Visualize circular trajectory arc."""
        traj = TrajectoryCircle(center=(5, 5), radius=3.0, angle_start=0, angle_end=360, vmax=2.0)
        
        # Generate visualization
        output_path = "/tmp/circle_trajectory_viz.html"
        result_path = visualize_trajectory_html(traj, "Full Circle", output_path)
        
        # Verify file created
        self.assertTrue(Path(result_path).exists())
        with open(result_path, 'r') as f:
            html = f.read()
            self.assertIn("Full Circle", html)
    
    def test_merged_trajectory_visualization(self):
        """Visualize merged/concatenated trajectory."""
        seg1 = TrajectoryPolygon([(0, 0), (5, 0), (5, 5)], vmax=3.0)
        seg2 = TrajectoryCircle(center=(5, 5), radius=2.0, angle_start=0, angle_end=180, vmax=2.0)
        
        merged = TrajectoryMerged([seg1, seg2])
        
        # Generate visualization
        output_path = "/tmp/merged_trajectory_viz.html"
        result_path = visualize_trajectory_html(merged, "Polygon + Circle", output_path)
        
        # Verify file created
        self.assertTrue(Path(result_path).exists())


class TestAnimationTimelineVisualization(unittest.TestCase):
    """Test Animation timeline visualization."""
    
    def test_animation_timeline_visualization(self):
        """Visualize animation frame sequence."""
        timeline = AnimationTimeline()
        
        # Simulate AGV moving along trajectory
        waypoints = [(0, 0), (10, 0), (10, 10)]
        traj = TrajectoryPolygon(waypoints, vmax=5.0)
        
        # Sample positions at different times
        for t in [0.0, 0.5, 1.0, 1.5, 2.0]:
            x, y = traj.position(t)
            state = {
                "name": "AGV_01",
                "x": x,
                "y": y,
                "z": 0.0,
                "rotation": 45.0 + t * 10,
                "color": "blue",
                "size": 5,
                "timestamp": t,
            }
            timeline.add_frame(t, state)
        
        # Generate visualization
        output_path = "/tmp/animation_timeline_viz.html"
        result_path = visualize_animation_timeline_html(timeline, "AGV Animation Timeline", output_path)
        
        # Verify file created
        self.assertTrue(Path(result_path).exists())
        with open(result_path, 'r') as f:
            html = f.read()
            self.assertIn("AGV_01", html)
            self.assertIn("AGV Animation Timeline", html)
            self.assertIn("Frame", html)


class TestIntegratedVisualization(unittest.TestCase):
    """Test integrated visualization of multiple components."""
    
    def test_complete_system_visualization(self):
        """Create visualizations for Monitor, Resource, Trajectory, Animation."""
        visualizations = {}
        
        # 1. Monitor visualization
        monitor = LevelMonitor(name="System Queue")
        for t, val in [(0, 0), (1, 2), (2, 5), (3, 3), (4, 1), (5, 0)]:
            monitor.tally(t, val)
        
        output = "/tmp/demo_monitor.html"
        visualizations["Monitor (Queue Length)"] = visualize_monitor_html(monitor, "System Queue", output)
        
        # 2. Resource visualization
        env = Environment()
        resource = Resource("Worker", capacity=3, env=env)
        
        # Simulate activity
        class Agent:
            pass
        
        ag = Agent()
        resource.request(ag, 1)
        resource.capacity_monitor.tally(0, 3)
        resource.available_monitor.tally(0, 2)
        resource.claimed_monitor.tally(0, 1)
        
        output = "/tmp/demo_resource.html"
        visualizations["Resource (Capacity)"] = visualize_resource_html(resource, output)
        
        # 3. Trajectory visualization
        traj = TrajectoryPolygon([(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)], vmax=2.0)
        output = "/tmp/demo_trajectory.html"
        visualizations["Trajectory (Square Path)"] = visualize_trajectory_html(traj, output_path=output)
        
        # 4. Animation timeline
        timeline = AnimationTimeline()
        for t in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
            x, y = traj.position(t)
            timeline.add_frame(t, {
                "name": "Robot",
                "x": x,
                "y": y,
                "timestamp": t,
                "color": "green",
            })
        
        output = "/tmp/demo_animation.html"
        visualizations["Animation Timeline"] = visualize_animation_timeline_html(timeline, output_path=output)
        
        # Print summary
        print_visualization_summary(visualizations)
        
        # Verify all files exist
        for name, path in visualizations.items():
            self.assertTrue(Path(path).exists(), f"Missing visualization: {name}")
    
    def test_json_exports(self):
        """Test JSON export of various components."""
        exports = {}
        
        # Monitor JSON
        monitor = LevelMonitor("test")
        monitor.tally(0, 5)
        monitor.tally(10, 8)
        
        anim = AnimateMonitor(monitor)
        json_str = anim.to_json()
        exports["Monitor JSON"] = json.loads(json_str)
        
        # Animation timeline JSON
        timeline = AnimationTimeline()
        timeline.add_frame(0, {"name": "obj", "x": 0, "y": 0, "timestamp": 0})
        timeline.add_frame(1, {"name": "obj", "x": 1, "y": 1, "timestamp": 1})
        
        exports["Timeline JSON"] = timeline.to_dict()
        
        # Verify structure
        self.assertIn("time", exports["Monitor JSON"])
        self.assertIn("values", exports["Monitor JSON"])
        self.assertIn("times", exports["Timeline JSON"])
        self.assertIn("frames", exports["Timeline JSON"])
        
        # Print exports
        print("\n" + "=" * 70)
        print("JSON EXPORTS")
        print("=" * 70)
        for name, data in exports.items():
            print(f"\n{name}:")
            print(json.dumps(data, indent=2)[:200] + "...")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    unittest.main()
