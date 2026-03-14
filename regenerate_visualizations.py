#!/usr/bin/env python3
"""Regenerate all visualizations to the visualizations folder."""

from pathlib import Path
import json
import sys

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from tests.test_visualization import (
    visualize_monitor_html,
    visualize_resource_html,
    visualize_trajectory_html,
    visualize_animation_timeline_html,
    print_visualization_summary
)
from hsim.core.des.resources import Resource
from hsim.core.des.trajectory import TrajectoryPolygon, TrajectoryCircle, TrajectoryMerged
from hsim.core.stats.animation import AnimateMonitor, AnimationTimeline


def _sample_trajectory(traj, sim_horizon: float, dt: float = 0.1):
        """Sample a trajectory as repeating movement for live playback."""
        samples = []
        t = 0.0
        duration = max(traj.duration, 1e-6)
        while t <= sim_horizon + 1e-9:
                local_t = t % duration
                x, y = traj.position(local_t)
                samples.append({"t": round(t, 4), "x": float(x), "y": float(y)})
                t += dt
        return samples


def _build_live_salabim_like_view(output_path: Path) -> str:
        """Generate a live, time-flowing HTML animation with play/pause/speed controls."""
        sim_horizon = 60.0
        dt = 0.1

        main_loop = TrajectoryPolygon([(5, 5), (95, 5), (95, 45), (5, 45), (5, 5)], vmax=9)
        side_arc = TrajectoryCircle(center=(50, 25), radius=12, vmax=8, angle_start=0, angle_end=360)
        merged = TrajectoryMerged([main_loop, side_arc])

        agv_1 = _sample_trajectory(main_loop, sim_horizon, dt)
        agv_2 = _sample_trajectory(merged, sim_horizon, dt)

        monitor_points = []
        resource_points = []
        t = 0.0
        while t <= sim_horizon + 1e-9:
                queue_len = max(0.0, 2.0 + 2.0 * __import__("math").sin(t / 4.0) + 1.5 * __import__("math").sin(t / 1.7))
                occupancy = min(1.0, max(0.0, 0.35 + 0.3 * __import__("math").sin(t / 5.5) + 0.2 * __import__("math").cos(t / 2.8)))
                monitor_points.append({"t": round(t, 4), "value": round(queue_len, 3)})
                resource_points.append({"t": round(t, 4), "value": round(occupancy, 3)})
                t += dt

        payload = {
                "horizon": sim_horizon,
                "dt": dt,
                "agv1": agv_1,
                "agv2": agv_2,
                "queue": monitor_points,
                "occupancy": resource_points,
        }

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Salabim-like Live Simulation</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        :root {{
            --bg: #0f172a;
            --panel: #111827;
            --line: #334155;
            --text: #e5e7eb;
            --muted: #94a3b8;
            --accent: #22c55e;
            --accent2: #38bdf8;
            --warn: #f59e0b;
        }}
        body {{ margin: 0; font-family: "Trebuchet MS", "Segoe UI", sans-serif; background: radial-gradient(circle at 20% 10%, #1e293b 0%, #0b1220 45%, #070b14 100%); color: var(--text); }}
        .wrap {{ max-width: 1280px; margin: 18px auto; padding: 0 14px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
        .title {{ font-size: 24px; font-weight: 800; letter-spacing: 0.3px; }}
        .sub {{ color: var(--muted); font-size: 13px; }}
        .board {{ display: grid; grid-template-columns: 2fr 1fr; gap: 14px; }}
        .panel {{ background: linear-gradient(165deg, #111827, #0b1220); border: 1px solid var(--line); border-radius: 12px; padding: 12px; box-shadow: 0 10px 22px rgba(0,0,0,0.28); }}
        .canvasbox {{ position: relative; }}
        #sim {{ width: 100%; height: 460px; border: 1px solid #334155; border-radius: 8px; background: #0a101d; }}
        .hud {{ position: absolute; top: 10px; left: 10px; background: rgba(2,6,23,0.85); border: 1px solid #334155; border-radius: 8px; padding: 8px 10px; font-size: 13px; }}
        .controls {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 10px; }}
        button, select {{ background: #1e293b; color: var(--text); border: 1px solid #475569; border-radius: 8px; padding: 7px 10px; cursor: pointer; }}
        button:hover, select:hover {{ border-color: #94a3b8; }}
        input[type=range] {{ width: 280px; }}
        .label {{ color: var(--muted); font-size: 12px; }}
        .metric {{ display: grid; grid-template-columns: 1fr auto; border-bottom: 1px solid #253449; padding: 7px 0; font-size: 13px; }}
        .metric:last-child {{ border-bottom: none; }}
        .value {{ font-family: "Consolas", monospace; color: #d1fae5; }}
        .plot {{ height: 215px; margin-top: 8px; }}
        @media (max-width: 980px) {{
            .board {{ grid-template-columns: 1fr; }}
            input[type=range] {{ width: 180px; }}
        }}
    </style>
</head>
<body>
    <div class="wrap">
        <div class="header">
            <div>
                <div class="title">Salabim-like Live Simulation View</div>
                <div class="sub">Simulation clock flows continuously. Entities move in real time with playback controls.</div>
            </div>
            <div class="sub">hsim / live renderer</div>
        </div>

        <div class="board">
            <div class="panel">
                <div class="canvasbox">
                    <canvas id="sim" width="940" height="460"></canvas>
                    <div class="hud" id="hud">t = 0.00</div>
                </div>
                <div class="controls">
                    <button id="playPause">Pause</button>
                    <button id="reset">Reset</button>
                    <span class="label">Speed</span>
                    <select id="speed">
                        <option value="0.5">0.5x</option>
                        <option value="1" selected>1x</option>
                        <option value="2">2x</option>
                        <option value="4">4x</option>
                    </select>
                    <span class="label">Time</span>
                    <input id="timeSlider" type="range" min="0" max="60" step="0.1" value="0" />
                    <span id="timeText" class="value">0.00 / 60.00</span>
                </div>
            </div>

            <div class="panel">
                <div class="metric"><span>Queue Length</span><span class="value" id="queueNow">0.00</span></div>
                <div class="metric"><span>Resource Occupancy</span><span class="value" id="occNow">0.00</span></div>
                <div class="metric"><span>AGV-1 Position</span><span class="value" id="agv1Now">(0.00, 0.00)</span></div>
                <div class="metric"><span>AGV-2 Position</span><span class="value" id="agv2Now">(0.00, 0.00)</span></div>
                <div id="queuePlot" class="plot"></div>
                <div id="occPlot" class="plot"></div>
            </div>
        </div>
    </div>

    <script>
        const data = {json.dumps(payload)};
        const canvas = document.getElementById('sim');
        const ctx = canvas.getContext('2d');
        const hud = document.getElementById('hud');
        const playPause = document.getElementById('playPause');
        const resetBtn = document.getElementById('reset');
        const speedSel = document.getElementById('speed');
        const slider = document.getElementById('timeSlider');
        const timeText = document.getElementById('timeText');

        const queueNow = document.getElementById('queueNow');
        const occNow = document.getElementById('occNow');
        const agv1Now = document.getElementById('agv1Now');
        const agv2Now = document.getElementById('agv2Now');

        let simTime = 0;
        let playing = true;
        let speed = 1;
        let lastWall = performance.now();
        let lastPlotRefresh = 0;

        slider.max = String(data.horizon);

        function pick(series, t) {{
            const idx = Math.max(0, Math.min(series.length - 1, Math.floor(t / data.dt)));
            return series[idx];
        }}

        function worldToCanvas(x, y) {{
            const px = 40 + (x / 100) * (canvas.width - 80);
            const py = canvas.height - (40 + (y / 50) * (canvas.height - 80));
            return [px, py];
        }}

        function drawLayout() {{
            ctx.fillStyle = '#0a101d';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.strokeStyle = '#1f2a44';
            ctx.lineWidth = 1;
            for (let gx = 40; gx <= canvas.width - 40; gx += 30) {{
                ctx.beginPath(); ctx.moveTo(gx, 30); ctx.lineTo(gx, canvas.height - 30); ctx.stroke();
            }}
            for (let gy = 30; gy <= canvas.height - 30; gy += 30) {{
                ctx.beginPath(); ctx.moveTo(40, gy); ctx.lineTo(canvas.width - 40, gy); ctx.stroke();
            }}

            ctx.strokeStyle = '#3b82f6';
            ctx.lineWidth = 3;
            ctx.strokeRect(40, 40, canvas.width - 80, canvas.height - 80);

            // Station blocks for salabim-like floor plan
            ctx.fillStyle = '#1f2937';
            ctx.strokeStyle = '#64748b';
            const stations = [
                [120, 90, 120, 60, 'S1'],
                [690, 90, 120, 60, 'S2'],
                [120, 300, 120, 60, 'S3'],
                [690, 300, 120, 60, 'S4'],
            ];
            ctx.font = '12px Trebuchet MS';
            ctx.fillStyle = '#1e293b';
            stations.forEach(([x, y, w, h, label]) => {{
                ctx.fillStyle = '#111827';
                ctx.fillRect(x, y, w, h);
                ctx.strokeStyle = '#64748b';
                ctx.strokeRect(x, y, w, h);
                ctx.fillStyle = '#cbd5e1';
                ctx.fillText(label, x + 8, y + 18);
            }});
        }}

        function drawAgv(x, y, color, label) {{
            const [px, py] = worldToCanvas(x, y);
            ctx.beginPath();
            ctx.fillStyle = color;
            ctx.arc(px, py, 9, 0, Math.PI * 2);
            ctx.fill();
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#e2e8f0';
            ctx.stroke();
            ctx.fillStyle = '#e2e8f0';
            ctx.font = '11px Trebuchet MS';
            ctx.fillText(label, px + 12, py - 10);
        }}

        function refreshPlots(force = false) {{
            if (!force && simTime - lastPlotRefresh < 0.2) return;
            lastPlotRefresh = simTime;

            const n = Math.max(1, Math.floor(simTime / data.dt));
            const qx = data.queue.slice(0, n).map(p => p.t);
            const qy = data.queue.slice(0, n).map(p => p.value);
            const ox = data.occupancy.slice(0, n).map(p => p.t);
            const oy = data.occupancy.slice(0, n).map(p => p.value);

            Plotly.react('queuePlot', [{{ x: qx, y: qy, mode: 'lines', line: {{ color: '#22c55e', width: 2 }} }}], {{
                margin: {{ l: 40, r: 12, t: 28, b: 30 }},
                title: 'Queue Length (live)',
                paper_bgcolor: '#111827',
                plot_bgcolor: '#0b1220',
                font: {{ color: '#e5e7eb' }},
                xaxis: {{ title: 't' }}, yaxis: {{ title: 'items' }}
            }}, {{displayModeBar: false}});

            Plotly.react('occPlot', [{{ x: ox, y: oy, mode: 'lines', line: {{ color: '#38bdf8', width: 2 }} }}], {{
                margin: {{ l: 40, r: 12, t: 28, b: 30 }},
                title: 'Resource Occupancy (live)',
                paper_bgcolor: '#111827',
                plot_bgcolor: '#0b1220',
                font: {{ color: '#e5e7eb' }},
                xaxis: {{ title: 't' }}, yaxis: {{ title: 'ratio', range: [0, 1] }}
            }}, {{displayModeBar: false}});
        }}

        function render() {{
            drawLayout();
            const p1 = pick(data.agv1, simTime);
            const p2 = pick(data.agv2, simTime);
            const q = pick(data.queue, simTime);
            const o = pick(data.occupancy, simTime);

            drawAgv(p1.x, p1.y, '#f59e0b', 'AGV-1');
            drawAgv(p2.x, p2.y, '#38bdf8', 'AGV-2');

            hud.textContent = `t = ${{simTime.toFixed(2)}}`;
            timeText.textContent = `${{simTime.toFixed(2)}} / ${{data.horizon.toFixed(2)}}`;
            slider.value = simTime.toFixed(2);

            queueNow.textContent = q.value.toFixed(2);
            occNow.textContent = o.value.toFixed(2);
            agv1Now.textContent = `(${{p1.x.toFixed(2)}}, ${{p1.y.toFixed(2)}})`;
            agv2Now.textContent = `(${{p2.x.toFixed(2)}}, ${{p2.y.toFixed(2)}})`;

            refreshPlots();
        }}

        function tick(now) {{
            const wallDelta = (now - lastWall) / 1000.0;
            lastWall = now;
            if (playing) {{
                simTime += wallDelta * speed;
                if (simTime > data.horizon) simTime = 0;
            }}
            render();
            requestAnimationFrame(tick);
        }}

        playPause.onclick = () => {{
            playing = !playing;
            playPause.textContent = playing ? 'Pause' : 'Play';
        }};
        resetBtn.onclick = () => {{
            simTime = 0;
            refreshPlots(true);
            render();
        }};
        speedSel.onchange = () => {{ speed = Number(speedSel.value); }};
        slider.oninput = () => {{ simTime = Number(slider.value); render(); }};

        refreshPlots(true);
        render();
        requestAnimationFrame(tick);
    </script>
</body>
</html>
"""

        output_path.write_text(html)
        return str(output_path)

# Create visualizations folder
viz_folder = Path(__file__).parent / "visualizations"
viz_folder.mkdir(exist_ok=True)

visualizations = {}

# 1. Level Monitor Visualization (mock)
print("Generating Level Monitor visualization...")
class MockMonitor:
    def __init__(self, name, values):
        self.name = name
        self._timestamps = list(range(len(values)))
        self._values = values

monitor = MockMonitor("Queue Length", [0.0, 2.0, 5.0, 3.0, 1.0, 0.0])
visualizations["Level Monitor"] = visualize_monitor_html(
    monitor,
    title="Queue Length Over Time",
    output_path=str(viz_folder / "level_monitor_viz.html")
)

# 2. Non-Level Monitor Visualization
print("Generating Non-Level Monitor visualization...")
non_level_monitor = MockMonitor("Service Times", [0.5, 1.2, 0.8, 1.5, 0.9, 1.1, 1.4, 0.7])
visualizations["Non-Level Monitor"] = visualize_monitor_html(
    non_level_monitor,
    title="Service Times",
    output_path=str(viz_folder / "non_level_monitor_viz.html")
)

# 3. Resource Visualization (mock)
print("Generating Resource Visualization...")
class MockResource:
    def __init__(self, name):
        self.name = name
        self.capacity_monitor = MockMonitor("Capacity", [5, 5, 5, 5, 5])
        self.available_monitor = MockMonitor("Available", [5, 4, 2, 3, 5])
        self.claimed_monitor = MockMonitor("Claimed", [0, 1, 3, 2, 0])
        self.occupancy_monitor = MockMonitor("Occupancy", [0.0, 0.2, 0.6, 0.4, 0.0])

resource = MockResource("Assembly Station")
visualizations["Resource"] = visualize_resource_html(
    resource,
    output_path=str(viz_folder / "resource_viz.html")
)

# 4. Polygon Trajectory Visualization
print("Generating Polygon Trajectory visualization...")
polygon_trajectory = TrajectoryPolygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], vmax=10)
visualizations["Polygon Trajectory"] = visualize_trajectory_html(
    polygon_trajectory,
    title="Square Path",
    output_path=str(viz_folder / "polygon_trajectory_viz.html")
)

# 5. Circle Trajectory Visualization
print("Generating Circle Trajectory visualization...")
circle_trajectory = TrajectoryCircle(
    center=(5, 5),
    radius=3,
    angle_start=0,
    angle_end=360,
    vmax=10
)
visualizations["Circle Trajectory"] = visualize_trajectory_html(
    circle_trajectory,
    title="Full Circle Arc",
    output_path=str(viz_folder / "circle_trajectory_viz.html")
)

# 6. Merged Trajectory Visualization
print("Generating Merged Trajectory visualization...")
polygon = TrajectoryPolygon([(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)], vmax=10)
circle = TrajectoryCircle(center=(5, 5), radius=2, angle_start=0, angle_end=180, vmax=10)
merged_trajectory = TrajectoryMerged([polygon, circle])
visualizations["Merged Trajectory"] = visualize_trajectory_html(
    merged_trajectory,
    title="Polygon + Circle Arc",
    output_path=str(viz_folder / "merged_trajectory_viz.html")
)

# 7. Animation Timeline Visualization
print("Generating Animation Timeline visualization...")
timeline = AnimationTimeline()
timeline.add_frame(0.0, {"name": "AGV-01", "x": 0, "y": 0, "color": "blue", "rotation": 0})
timeline.add_frame(1.0, {"name": "AGV-01", "x": 2.5, "y": 2.5, "color": "green", "rotation": 45})
timeline.add_frame(2.0, {"name": "AGV-01", "x": 5, "y": 5, "color": "orange", "rotation": 90})
timeline.add_frame(3.0, {"name": "AGV-01", "x": 7.5, "y": 2.5, "color": "red", "rotation": 135})
timeline.add_frame(4.0, {"name": "AGV-01", "x": 10, "y": 0, "color": "purple", "rotation": 180})
visualizations["Animation Timeline"] = visualize_animation_timeline_html(
    timeline,
    title="AGV Movement Timeline",
    output_path=str(viz_folder / "animation_timeline_viz.html")
)

# 8. Live salabim-like playback (time-flowing, non-static)
print("Generating live salabim-like playback...")
visualizations["Live Salabim-like"] = _build_live_salabim_like_view(
    viz_folder / "salabim_live_simulation.html"
)

# Print summary
print_visualization_summary(visualizations)
print(f"\n✅ All visualizations saved to: {viz_folder.absolute()}")

