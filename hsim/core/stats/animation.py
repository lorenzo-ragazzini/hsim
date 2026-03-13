"""Animation bridge for DES simulations.

Provides utilities for exporting simulation state and Monitor data in web-ready formats:
- Monitor time-series data as Plotly figures
- Animation state as JSON for web renderers
- Animation state protocol documentation via animation_state() method signature
"""

from typing import Any, Dict, List, Optional, Callable
import json


class AnimateMonitor:
    """Wrapper for Monitor data visualization via Plotly.
    
    Converts Monitor time-series (._t, ._x arrays) into Plotly figures
    suitable for embedding in web dashboards.
    
    Example:
        monitor = LevelMonitor(env, capacity=10)
        # ... simulation runs, monitor collects data ...
        anim = AnimateMonitor(monitor, name="Queue Length", title="Queue Over Time")
        fig = anim.to_plotly_scatter()  # Returns go.Scatter compatible dict
        fig_html = anim.to_html()       # HTML string for embedding
    """
    
    def __init__(
        self,
        monitor,
        name: str = "Monitor",
        title: Optional[str] = None,
        xlabel: str = "Time",
        ylabel: Optional[str] = None,
        color: str = "blue",
    ):
        """Initialize AnimateMonitor.
        
        Args:
            monitor: Monitor object (LevelMonitor or NonLevelMonitor)
            name: Name for legend/display
            title: Plot title (defaults to monitor name)
            xlabel: X-axis label
            ylabel: Y-axis label (defaults to monitor name)
            color: Line color for Plotly
        """
        self.monitor = monitor
        self.name = name
        self.title = title or name
        self.xlabel = xlabel
        self.ylabel = ylabel or name
        self.color = color
    
    def to_plotly_dict(self) -> Dict[str, Any]:
        """Export as Plotly Scatter trace dict (compatible with go.Scatter).
        
        Returns:
            dict with keys: x, y, mode, name, line, hovertemplate
        """
        # Check for LevelMonitor (_timestamps, _values)
        if hasattr(self.monitor, "_timestamps") and hasattr(self.monitor, "_values"):
            t_data = list(self.monitor._timestamps) if self.monitor._timestamps else []
            x_data = list(self.monitor._values) if self.monitor._values else []
        # Check for NonLevelMonitor (_values array exists but needs time axis setup)
        elif hasattr(self.monitor, "_values"):
            # For NonLevelMonitor, use index as x-axis
            x_data = list(self.monitor._values) if self.monitor._values else []
            t_data = list(range(len(x_data)))
        else:
            t_data = []
            x_data = []
        
        return {
            "x": t_data,
            "y": x_data,
            "mode": "lines",
            "name": self.name,
            "line": {"color": self.color, "width": 2},
            "hovertemplate": f"{self.xlabel}: %{{x:.2f}}<br>{self.ylabel}: %{{y:.2f}}<extra></extra>",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Export as simple dict: {'time': [...], 'values': [...]}.
        
        Returns:
            dict with keys: name, title, time, values
        """
        # Check for LevelMonitor (_timestamps, _values)
        if hasattr(self.monitor, "_timestamps") and hasattr(self.monitor, "_values"):
            t_data = list(self.monitor._timestamps) if self.monitor._timestamps else []
            x_data = list(self.monitor._values) if self.monitor._values else []
        # Check for NonLevelMonitor (_values array)
        elif hasattr(self.monitor, "_values"):
            x_data = list(self.monitor._values) if self.monitor._values else []
            t_data = list(range(len(x_data)))
        else:
            t_data = []
            x_data = []
        
        return {
            "name": self.name,
            "title": self.title,
            "time": t_data,
            "values": x_data,
        }
    
    def to_json(self) -> str:
        """Export as JSON string.
        
        Returns:
            JSON string of monitor data
        """
        return json.dumps(self.to_dict(), default=str)
    
    def to_html(self, include_plotly_cdn: bool = True) -> str:
        """Generate standalone HTML with embedded Plotly figure.
        
        Args:
            include_plotly_cdn: if True, includes CDN link to plotly.js
        
        Returns:
            HTML string ready for embedding or writing to file
        """
        import json as json_module
        
        plotly_trace = self.to_plotly_dict()
        
        html = ""
        if include_plotly_cdn:
            html += '<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>\n'
        
        html += f'<div id="plot-{id(self)}" style="width:100%;height:500px;"></div>\n'
        html += '<script>\n'
        html += f'var data = [{json_module.dumps(plotly_trace)}];\n'
        html += f'var layout = {{\n'
        html += f'  title: "{self.title}",\n'
        html += f'  xaxis: {{ title: "{self.xlabel}" }},\n'
        html += f'  yaxis: {{ title: "{self.ylabel}" }},\n'
        html += f'  hovermode: "closest"\n'
        html += f'}};\n'
        html += f'Plotly.newPlot("plot-{id(self)}", data, layout);\n'
        html += '</script>\n'
        
        return html


def serialize_animation_state(state: Dict[str, Any]) -> str:
    """Serialize animation state dictionary to JSON.
    
    Handles common types: float, int, str, list, dict, None.
    
    Args:
        state: Animation state dict from TrajectoryFollower.animation_state()
               Expected keys: name, x, y, z, rotation, color, size, timestamp
    
    Returns:
        JSON string representation
    """
    return json.dumps(state, default=str)


def deserialize_animation_state(json_str: str) -> Dict[str, Any]:
    """Deserialize animation state from JSON.
    
    Args:
        json_str: JSON string from serialize_animation_state()
    
    Returns:
        Animation state dict
    
    Raises:
        json.JSONDecodeError: if JSON is malformed
    """
    return json.loads(json_str)


class AnimationTimeline:
    """Manages a sequence of animation frames for playback.
    
    Stores animation states at discrete time points and provides
    utilities for interpolation and export.
    
    Example:
        timeline = AnimationTimeline()
        for t in sim_times:
            state = agv.animation_state(t)
            timeline.add_frame(t, state)
        frames = timeline.get_frames()
        """
    
    def __init__(self):
        """Initialize empty timeline."""
        self.frames: List[tuple] = []  # List of (time, state_dict)
    
    def add_frame(self, time: float, state: Dict[str, Any]) -> None:
        """Add animation frame at a specific time.
        
        Args:
            time: Simulation time
            state: Animation state dict
        """
        self.frames.append((time, state))
    
    def get_frames(self) -> List[tuple]:
        """Retrieve all frames in order.
        
        Returns:
            List of (time, state_dict) tuples
        """
        return sorted(self.frames, key=lambda f: f[0])
    
    def to_json(self, include_times: bool = True) -> str:
        """Export timeline as JSON.
        
        Args:
            include_times: if True, includes time field in each frame
        
        Returns:
            JSON string of frames
        """
        frames_data = []
        for t, state in self.get_frames():
            frame = dict(state)  # copy
            if include_times:
                frame["_time"] = t
            frames_data.append(frame)
        
        return json.dumps(frames_data, default=str)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export timeline as structured dict.
        
        Returns:
            dict with keys: times, frames (each frame is dict with animation state)
        """
        times = []
        frames = []
        for t, state in self.get_frames():
            times.append(t)
            frames.append(state)
        
        return {
            "times": times,
            "frames": frames,
        }


def animation_state_template() -> Dict[str, Any]:
    """Return template for animation_state() protocol.
    
    This documents the standard animation state format that all
    animated agents should return from animation_state(t).
    
    Returns:
        Example animation state dict with common fields
    
    Example:
        class AGV:
            def animation_state(self, t: float) -> dict:
                # Follow the template below
                return animation_state_template()
    """
    return {
        "name": "entity_name",        # str: unique identifier
        "x": 0.0,                      # float: x position
        "y": 0.0,                      # float: y position
        "z": 0.0,                      # float: z position (optional, default 0)
        "rotation": 0.0,               # float: rotation angle in degrees
        "color": "blue",               # str: CSS color or hex
        "size": 10,                    # float or int: display size (radius, marker size)
        "timestamp": 0.0,              # float: simulation time for this state
        "shape": "circle",             # str: shape type (circle, rect, triangle, etc)
        "opacity": 1.0,                # float: alpha transparency 0-1
        "label": "",                   # str: display label (optional)
    }


def validate_animation_state(state: Dict[str, Any]) -> bool:
    """Validate animation state dict has required fields.
    
    Args:
        state: Animation state dict
    
    Returns:
        True if state has all required fields (name, x, y, timestamp)
    """
    required = {"name", "x", "y", "timestamp"}
    return all(k in state for k in required)
