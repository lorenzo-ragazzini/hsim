"""Visualization utilities for DES test fixtures.

Generates HTML visualizations, Plotly figures, and JSON exports of:
- Monitor time-series data
- Resource occupancy and capacity
- Trajectory paths
- Animation timelines
"""

import json
import math
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path


def visualize_monitor_html(
    monitor,
    title: str = "Monitor Data",
    output_path: str = "/tmp/monitor_visualization.html"
) -> str:
    """Generate interactive HTML visualization of Monitor data.
    
    Args:
        monitor: LevelMonitor or NonLevelMonitor instance
        title: Plot title
        output_path: Path to write HTML file
    
    Returns:
        Path to generated HTML file
    """
    from hsim.core.stats.animation import AnimateMonitor
    
    anim = AnimateMonitor(monitor, name=monitor.name or "Monitor", title=title, color="steelblue")
    html = anim.to_html(include_plotly_cdn=True)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path


def visualize_resource_html(
    resource,
    output_path: str = "/tmp/resource_visualization.html"
) -> str:
    """Generate HTML visualization of Resource monitoring data.
    
    Visualizes capacity usage, available units, claimed units, and occupancy.
    
    Args:
        resource: Resource instance
        output_path: Path to write HTML file
    
    Returns:
        Path to generated HTML file
    """
    from hsim.core.stats.animation import AnimateMonitor
    
    html = """<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <title>Resource Visualization</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .plot { width: 100%; height: 500px; margin-bottom: 30px; }
        h1 { color: #333; }
        h2 { color: #666; margin-top: 30px; }
    </style>
</head>
<body>
    <h1>Resource: """ + (resource.name or "Resource") + """</h1>
    <h2>Capacity</h2>
    <div id="plot-capacity" class="plot"></div>
    
    <h2>Available Units</h2>
    <div id="plot-available" class="plot"></div>
    
    <h2>Claimed Units</h2>
    <div id="plot-claimed" class="plot"></div>
    
    <h2>Occupancy</h2>
    <div id="plot-occupancy" class="plot"></div>
    
    <script>
"""
    
    # Create Plotly traces for each monitor
    monitors = [
        ("capacity", resource.capacity_monitor, "Capacity"),
        ("available", resource.available_monitor, "Available Units"),
        ("claimed", resource.claimed_monitor, "Claimed Units"),
        ("occupancy", resource.occupancy_monitor, "Occupancy"),
    ]
    
    for plot_id, monitor, label in monitors:
        if hasattr(monitor, "_timestamps") and hasattr(monitor, "_values"):
            t_data = list(monitor._timestamps)
            x_data = list(monitor._values)
        else:
            t_data = []
            x_data = []
        
        trace_dict = {
            "x": t_data,
            "y": x_data,
            "mode": "lines",
            "name": label,
            "line": {"width": 2},
        }
        
        html += f"""        var trace_{plot_id} = {json.dumps(trace_dict)};
        var layout_{plot_id} = {{
            title: '{label}',
            xaxis: {{ title: 'Time' }},
            yaxis: {{ title: 'Units' }},
            hovermode: 'closest'
        }};
        Plotly.newPlot('plot-{plot_id}', [trace_{plot_id}], layout_{plot_id});
"""
    
    html += """    </script>
</body>
</html>"""
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path


def visualize_trajectory_html(
    trajectory,
    title: str = "Trajectory Visualization",
    output_path: str = "/tmp/trajectory_visualization.html"
) -> str:
    """Generate HTML visualization of Trajectory path.
    
    Args:
        trajectory: Trajectory object (Polygon, Circle, Merged, etc.)
        title: Plot title
        output_path: Path to write HTML file
    
    Returns:
        Path to generated HTML file
    """
    from hsim.core.des.trajectory import TrajectoryPolygon, TrajectoryCircle, TrajectoryMerged
    
    # Extract waypoints for visualization
    waypoints = []
    
    if isinstance(trajectory, TrajectoryPolygon):
        waypoints = list(trajectory.polygon)
    elif isinstance(trajectory, TrajectoryCircle):
        # Sample circle arc at intervals
        center = trajectory.center
        radius = trajectory.radius
        angle_start = trajectory.angle_start * math.pi / 180.0
        angle_end = trajectory.angle_end * math.pi / 180.0
        
        n_samples = 100
        for i in range(n_samples + 1):
            alpha = angle_start + (angle_end - angle_start) * i / n_samples
            x = center[0] + radius * math.cos(alpha)
            y = center[1] + radius * math.sin(alpha)
            waypoints.append((x, y))
    elif isinstance(trajectory, TrajectoryMerged):
        for seg in trajectory.trajectories:
            if isinstance(seg, TrajectoryPolygon):
                waypoints.extend(list(seg.polygon)[:-1])  # Avoid duplicate endpoints
            elif isinstance(seg, TrajectoryCircle):
                # Sample circle
                center = seg.center
                radius = seg.radius
                angle_start = seg.angle_start * math.pi / 180.0
                angle_end = seg.angle_end * math.pi / 180.0
                n_samples = 50
                for i in range(n_samples + 1):
                    alpha = angle_start + (angle_end - angle_start) * i / n_samples
                    x = center[0] + radius * math.cos(alpha)
                    y = center[1] + radius * math.sin(alpha)
                    waypoints.append((x, y))
        if waypoints and not waypoints[-1] == waypoints[-1]:
            # Add final point
            pass
    
    if not waypoints:
        waypoints = [(0, 0), (1, 1)]  # Fallback
    
    xs = [w[0] for w in waypoints]
    ys = [w[1] for w in waypoints]
    
    trace_dict = {
        "x": xs,
        "y": ys,
        "mode": "lines+markers",
        "name": "Path",
        "line": {"color": "blue", "width": 2},
        "marker": {"size": 4},
    }
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        #plot {{ width: 100%; height: 600px; }}
        h1 {{ color: #333; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div id="plot"></div>
    <script>
        var trace = {json.dumps(trace_dict)};
        var layout = {{
            title: '{title}',
            xaxis: {{ title: 'X' }},
            yaxis: {{ title: 'Y', scaleanchor: 'x', scaleratio: 1 }},
            hovermode: 'closest'
        }};
        Plotly.newPlot('plot', [trace], layout);
    </script>
</body>
</html>"""
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path


def visualize_animation_timeline_html(
    timeline,
    title: str = "Animation Timeline",
    output_path: str = "/tmp/animation_timeline.html"
) -> str:
    """Generate HTML visualization of animation timeline.
    
    Creates interactive table and timeline view of animation frames.
    
    Args:
        timeline: AnimationTimeline instance
        title: Page title
        output_path: Path to write HTML file
    
    Returns:
        Path to generated HTML file
    """
    frames = timeline.get_frames()
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{ background: #f9f9f9; }}
        .time {{ font-family: monospace; color: #0066cc; }}
        .state {{ font-family: monospace; font-size: 12px; }}
        .timeline-bar {{
            width: 30px;
            height: 20px;
            background: linear-gradient(to right, #4CAF50, #8BC34A);
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p>Total frames: {len(frames)}</p>
"""
    
    html += """    <table>
        <tr>
            <th>Frame #</th>
            <th>Time</th>
            <th>Entity Name</th>
            <th>Position (x, y)</th>
            <th>Color</th>
            <th>State</th>
        </tr>
"""
    
    for idx, (t, state) in enumerate(frames):
        name = state.get("name", "?")
        x = state.get("x", "?")
        y = state.get("y", "?")
        color = state.get("color", "gray")
        
        html += f"""        <tr>
            <td>{idx}</td>
            <td class="time">{t:.2f}</td>
            <td><strong>{name}</strong></td>
            <td>({x:.2f}, {y:.2f})</td>
            <td><span style="display:inline-block;width:20px;height:20px;background:{color};border-radius:2px;"></span> {color}</td>
            <td class="state">{json.dumps(state, default=str)}</td>
        </tr>
"""
    
    html += """    </table>
</body>
</html>"""
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path


def print_visualization_summary(visualizations: Dict[str, str]):
    """Print summary of generated visualizations.
    
    Args:
        visualizations: Dict of {name: filepath} pairs
    """
    print("\n" + "=" * 70)
    print("VISUALIZATION SUMMARY")
    print("=" * 70)
    for name, path in visualizations.items():
        if Path(path).exists():
            size = Path(path).stat().st_size
            print(f"✓ {name:30s} → {path} ({size:,} bytes)")
        else:
            print(f"✗ {name:30s} → {path} (NOT CREATED)")
    print("=" * 70 + "\n")


# Add missing import
import math
