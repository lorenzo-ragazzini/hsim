"""Trajectory classes for modeling paths, conveyors, and AGV movements."""

import math
from typing import List, Tuple, Optional, Callable
import numpy as np


class _Movement:
    """Internal: represents one segment of a trajectory."""
    
    def __init__(self, x1: float, y1: float, x2: float, y2: float, vmax: float):
        """Initialize a straight-line movement segment.
        
        Args:
            x1, y1: Starting point
            x2, y2: Ending point
            vmax: Maximum velocity (distance per time unit)
        """
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.vmax = vmax
        
        # Calculate distance and duration
        dx = x2 - x1
        dy = y2 - y1
        self.distance = math.sqrt(dx*dx + dy*dy)
        self.duration = self.distance / vmax if vmax > 0 else float('inf')
        
        # Unit direction vector
        if self.distance > 0:
            self.dx_unit = dx / self.distance
            self.dy_unit = dy / self.distance
        else:
            self.dx_unit = 0.0
            self.dy_unit = 0.0
    
    def position(self, t: float) -> Tuple[float, float]:
        """Get position at time t within this segment (0 <= t <= duration).
        
        Args:
            t: Time within segment
            
        Returns:
            (x, y) coordinates
        """
        if t <= 0:
            return (self.x1, self.y1)
        if t >= self.duration:
            return (self.x2, self.y2)
        
        distance_traveled = self.vmax * t
        x = self.x1 + self.dx_unit * distance_traveled
        y = self.y1 + self.dy_unit * distance_traveled
        return (x, y)
    
    def velocity(self) -> Tuple[float, float]:
        """Get velocity vector."""
        vx = self.vmax * self.dx_unit
        vy = self.vmax * self.dy_unit
        return (vx, vy)


class TrajectoryPolygon:
    """Linear trajectory following a polygon path.
    
    Example:
        traj = TrajectoryPolygon(
            polygon=[(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)],
            vmax=2.0
        )
    """
    
    def __init__(self, polygon: List[Tuple[float, float]], vmax: float):
        """Initialize polygon trajectory.
        
        Args:
            polygon: List of (x, y) waypoints
            vmax: Maximum velocity
        """
        self.polygon = polygon
        self.vmax = vmax
        self._movements = []
        self.duration = 0.0
        
        # Create movement segments between consecutive waypoints
        for i in range(len(polygon) - 1):
            x1, y1 = polygon[i]
            x2, y2 = polygon[i + 1]
            mov = _Movement(x1, y1, x2, y2, vmax)
            self._movements.append(mov)
            self.duration += mov.duration
    
    def x(self, t: float) -> float:
        """Get x coordinate at time t."""
        x, _ = self.position(t)
        return x
    
    def y(self, t: float) -> float:
        """Get y coordinate at time t."""
        _, y = self.position(t)
        return y
    
    def position(self, t: float) -> Tuple[float, float]:
        """Get (x, y) position at time t.
        
        Args:
            t: Time in trajectory (0 <= t <= duration)
            
        Returns:
            (x, y) coordinates
        """
        if t <= 0:
            return self.polygon[0]
        
        current_time = 0.0
        for mov in self._movements:
            if current_time + mov.duration >= t:
                # This segment contains the requested time
                segment_time = t - current_time
                return mov.position(segment_time)
            current_time += mov.duration
        
        # Beyond end of trajectory
        return self.polygon[-1]
    
    def segments(self) -> int:
        """Return number of segments."""
        return len(self._movements)


class TrajectoryCircle:
    """Circular trajectory (arc or full circle).
    
    Example:
        traj = TrajectoryCircle(
            center=(5, 5),
            radius=3.0,
            vmax=2.0,
            angle_start=0,
            angle_end=360
        )
    """
    
    def __init__(
        self,
        center: Tuple[float, float],
        radius: float,
        vmax: float,
        angle_start: float = 0,
        angle_end: float = 360
    ):
        """Initialize circular trajectory.
        
        Args:
            center: (x, y) center of circle
            radius: Radius of circle
            vmax: Maximum velocity (distance per time unit)
            angle_start: Starting angle in degrees (0=right, 90=top)
            angle_end: Ending angle in degrees
        """
        self.center = center
        self.radius = radius
        self.vmax = vmax
        self.angle_start = angle_start
        self.angle_end = angle_end
        
        # Calculate arc length
        angle_sweep = angle_end - angle_start
        arc_length = (angle_sweep / 360.0) * 2 * math.pi * radius
        self.duration = arc_length / vmax if vmax > 0 else float('inf')
    
    def x(self, t: float) -> float:
        """Get x coordinate at time t."""
        x, _ = self.position(t)
        return x
    
    def y(self, t: float) -> float:
        """Get y coordinate at time t."""
        _, y = self.position(t)
        return y
    
    def position(self, t: float) -> Tuple[float, float]:
        """Get (x, y) position at time t.
        
        Args:
            t: Time in trajectory
            
        Returns:
            (x, y) coordinates
        """
        if t <= 0:
            angle = self.angle_start
        elif t >= self.duration:
            angle = self.angle_end
        else:
            # Linear interpolation of angle
            progress = t / self.duration
            angle_sweep = self.angle_end - self.angle_start
            angle = self.angle_start + progress * angle_sweep
        
        # Convert angle to radians (0° = right, 90° = up)
        rad = math.radians(angle)
        cx, cy = self.center
        x = cx + self.radius * math.cos(rad)
        y = cy + self.radius * math.sin(rad)
        return (x, y)


class TrajectoryMerged:
    """Concatenated trajectory following multiple segments in sequence.
    
    Example:
        line = TrajectoryPolygon([(0, 0), (5, 0)], vmax=2)
        circle = TrajectoryCircle((5, 0), radius=2, vmax=2)
        merged = TrajectoryMerged([line, circle])
    """
    
    def __init__(self, trajectories: List):
        """Initialize merged trajectory.
        
        Args:
            trajectories: List of Trajectory objects to chain
        """
        self.trajectories = trajectories
        self._time_offsets = []
        self.duration = 0.0
        
        # Precompute time offsets for each trajectory
        for traj in trajectories:
            self._time_offsets.append(self.duration)
            self.duration += traj.duration
    
    def x(self, t: float) -> float:
        """Get x coordinate at time t."""
        x, _ = self.position(t)
        return x
    
    def y(self, t: float) -> float:
        """Get y coordinate at time t."""
        _, y = self.position(t)
        return y
    
    def position(self, t: float) -> Tuple[float, float]:
        """Get (x, y) position at time t.
        
        Args:
            t: Time in merged trajectory
            
        Returns:
            (x, y) coordinates
        """
        if t <= 0:
            return self.trajectories[0].position(0)
        if t >= self.duration:
            return self.trajectories[-1].position(self.trajectories[-1].duration)
        
        # Find which trajectory contains this time
        for i, traj in enumerate(self.trajectories):
            if t < self._time_offsets[i] + traj.duration:
                segment_time = t - self._time_offsets[i]
                return traj.position(segment_time)
        
        # Shouldn't reach here
        return self.trajectories[-1].position(self.trajectories[-1].duration)
    
    def segments(self) -> int:
        """Return number of trajectories in merge."""
        return len(self.trajectories)


# Animation helper for web visualization
class AnimationState:
    """Serializable animation frame for web renderer."""
    
    def __init__(
        self,
        name: str,
        x: float,
        y: float,
        z: float = 0.0,
        rotation: float = 0.0,
        color: str = "blue",
        size: float = 1.0
    ):
        """Initialize animation state.
        
        Args:
            name: Identifier for entity
            x, y, z: Position
            rotation: Rotation angle in degrees
            color: Color for visualization
            size: Size scaling factor
        """
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.rotation = rotation
        self.color = color
        self.size = size
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "rotation": self.rotation,
            "color": self.color,
            "size": self.size
        }


# Mixin for components that follow trajectories
class TrajectoryFollower:
    """Mixin for agents/components that follow a trajectory."""
    
    def __init__(self, trajectory):
        """Initialize with a trajectory.
        
        Args:
            trajectory: TrajectoryPolygon, TrajectoryCircle, or TrajectoryMerged
        """
        self.trajectory = trajectory
        self._start_time = 0.0
    
    def start_trajectory(self, at_time: float = 0.0):
        """Start following the trajectory.
        
        Args:
            at_time: Simulation time to start
        """
        self._start_time = at_time
    
    def get_position(self, current_time: float) -> Tuple[float, float]:
        """Get current position along trajectory.
        
        Args:
            current_time: Current simulation time
            
        Returns:
            (x, y) coordinates
        """
        elapsed = current_time - self._start_time
        return self.trajectory.position(max(0, elapsed))
    
    def animation_state(self, current_time: float, name: str = "agent", color: str = "blue") -> AnimationState:
        """Get animation state for web renderer.
        
        Args:
            current_time: Current simulation time
            name: Name/ID for entity
            color: Color for visualization
            
        Returns:
            AnimationState object ready for JSON export
        """
        x, y = self.get_position(current_time)
        elapsed = current_time - self._start_time
        rotation = 0.0  # Can be computed from trajectory direction
        
        return AnimationState(
            name=name,
            x=x,
            y=y,
            rotation=rotation,
            color=color
        )
