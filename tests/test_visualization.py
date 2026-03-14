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


def _wrap_html(title: str, style: str, body: str) -> str:
    """Wrap content in proper HTML structure."""
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{title}</title>\n"
        '  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>\n'
        f"  <style>{style}</style>\n"
        "</head>\n"
        "<body>\n"
        f"  <div class='container'>\n{body}\n  </div>\n"
        "</body>\n"
        "</html>"
    )


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
    plot_html = anim.to_html(include_plotly_cdn=False)
    
    style = (
        "body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; } "
        ".container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; "
        "border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); } "
        "h1 { color: #333; margin-top: 0; }"
    )
    
    body = f"    <h1>{title}</h1>\n    {plot_html}"
    html = _wrap_html(title, style, body)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path


def visualize_resource_html(
    resource,
    output_path: str = "/tmp/resource_visualization.html"
) -> str:
    """Generate HTML visualization of Resource monitoring data."""
    
    style = (
        "body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; } "
        ".container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; "
        "border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); } "
        "h1 { color: #333; margin-top: 0; } "
        ".plot { width: 100%; height: 500px; margin-bottom: 30px; } "
        "h2 { color: #666; margin-top: 30px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }"
    )
    
    body = f"    <h1>Resource: {resource.name or 'Resource'}</h1>\n"
    
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
        
        body += f"    <h2>{label}</h2>\n"
        body += f'    <div id="plot-{plot_id}" class="plot"></div>\n'
        body += (
            "    <script>\n"
            f"        var trace_{plot_id} = {json.dumps(trace_dict)};\n"
            f"        var layout_{plot_id} = {{\n"
            f"            title: '{label}',\n"
            f"            xaxis: {{ title: 'Time' }},\n"
            f"            yaxis: {{ title: 'Units' }},\n"
            f"            hovermode: 'closest'\n"
            f"        }};\n"
            f"        Plotly.newPlot('plot-{plot_id}', [trace_{plot_id}], layout_{plot_id});\n"
            "    </script>\n"
        )
    
    html = _wrap_html("Resource Visualization", style, body)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path


def visualize_trajectory_html(
    trajectory,
    title: str = "Trajectory Visualization",
    output_path: str = "/tmp/trajectory_visualization.html"
) -> str:
    """Generate HTML visualization of Trajectory path."""
    from hsim.core.des.trajectory import TrajectoryPolygon, TrajectoryCircle, TrajectoryMerged
    
    waypoints = []
    
    if isinstance(trajectory, TrajectoryPolygon):
        waypoints = list(trajectory.polygon)
    elif isinstance(trajectory, TrajectoryCircle):
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
                waypoints.extend(list(seg.polygon)[:-1])
            elif isinstance(seg, TrajectoryCircle):
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
    
    if not waypoints:
        waypoints = [(0, 0), (1, 1)]
    
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
    
    style = (
        "body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; } "
        ".container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; "
        "border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); } "
        "h1 { color: #333; margin-top: 0; } "
        "#plot { width: 100%; height: 600px; }"
    )
    
    body = (
        f"    <h1>{title}</h1>\n"
        f'    <div id="plot"></div>\n'
        f"    <script>\n"
        f"        var trace = {json.dumps(trace_dict)};\n"
        f"        var layout = {{\n"
        f"            title: '{title}',\n"
        f"            xaxis: {{ title: 'X' }},\n"
        f"            yaxis: {{ title: 'Y', scaleanchor: 'x', scaleratio: 1 }},\n"
        f"            hovermode: 'closest'\n"
        f"        }};\n"
        f"        Plotly.newPlot('plot', [trace], layout);\n"
        f"    </script>\n"
    )
    
    html = _wrap_html(title, style, body)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path


def visualize_animation_timeline_html(
    timeline,
    title: str = "Animation Timeline",
    output_path: str = "/tmp/animation_timeline.html"
) -> str:
    """Generate HTML visualization of animation timeline."""
    frames = timeline.get_frames()
    
    style = (
        "body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; } "
        ".container { max-words: 1400px; margin: 0 auto; background: white; padding: 20px; "
        "border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); } "
        "h1 { color: #333; margin-top: 0; } "
        "p { color: #666; } "
        "table { width: 100 percent; border-collapse: collapse; background: white; } "
        "th { background: #4CAF50; color: white; padding: 12px; text-align: left; font-weight: bold; } "
        "td { padding: 10px; border-bottom: 1px solid #ddd; } "
        "tr:hover { background: #f9f9f9; } "
        ".time { font-family: monospace; color: #0066cc; } "
        ".state { font-family: monospace; font-size: 12px; }"
    )
    
    body = f"    <h1>{title}</h1>\n"
    body += f"    <p>Total frames: {len(frames)}</p>\n"
    body += "    <table>\n"
    body += "      <tr>\n"
    body += "        <th>Frame #</th><th>Time</th><th>Entity Name</th><th>Position (x, y)</th><th>Color</th><th>State</th>\n"
    body += "      </tr>\n"
    
    for idx, (t, state) in enumerate(frames):
        name = state.get("name", "?")
        x = state.get("x", "?")
        y = state.get("y", "?")
        color = state.get("color", "gray")
        
        body += "      <tr>\n"
        body += f"        <td>{idx}</td><td class='time'>{t:.2f}</td><td><strong>{name}</strong></td>"
        body += f"<td>({x:.2f}, {y:.2f})</td>"
        body += f"<td><span style='display:inline-block;width:20px;height:20px;background:{color};border-radius:2px;'></span> {color}</td>"
        body += f"<td class='state'>{json.dumps(state, default=str)}</td>\n"
        body += "      </tr>\n"
    
    body += "    </table>\n"
    
    html = _wrap_html(title, style, body)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    
    return output_path


def print_visualization_summary(visualizations: Dict[str, str]):
    """Print summary of generated visualizations."""
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
