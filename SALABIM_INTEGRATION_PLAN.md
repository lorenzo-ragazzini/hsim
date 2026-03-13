# hsim × salabim Integration Plan

> Branch: `agentic` · Date: March 2026  
> Focus: **yieldless** salabim. Keep FSM-driven architecture, DES blocks, and reaktiv where justified.

---

## 1. What to borrow from salabim

### 1.1 Scheduler refinements (small delta, high value)

Current hsim scheduler is already heapq-based and structurally sound. Cherry-pick:

| Addition | Rationale |
|---|---|
| `urgent` flag in FEL tuple — sorts to front of same-`(time, priority)` bucket | Needed for interrupt/resume and preemptive resources |
| `cap_now` guard on `schedule()` / `schedule_absolute()` | Prevents silent bugs when a computed delay is slightly negative |
| `standby` queue — components re-evaluated every calendar step, never on FEL | Models "passive wait until something changes" without one-off events |

Do **not** adopt the greenlet/yieldless execution model. FSM callbacks are structurally cleaner.

---

### 1.2 Monitor — statistics layer (highest priority, nothing equivalent in hsim)

Port `Monitor` from salabim into `hsim/core/stats/monitor.py`.

Two modes:
- **Level Monitor** — tracks a piecewise-constant value over time (`queue.length`, `resource.occupancy`). Records `(time, value)` pairs. Computes time-weighted mean, std, percentile, histogram.
- **Non-level Monitor** — tallies individual samples (`sojourn_time`, `service_time`). Computes sample mean, std, percentile.

Implementation details:
- Back with `array.array('d')` and `array.array('L')` for memory efficiency at scale (4–5× smaller than Python lists; same append speed).
- `stats_only=True` mode: accumulate running mean/variance with Welford's algorithm, drop raw samples.
- `reset()` / `merge()` / `print_statistics()` / `histogram()` as salabim API.
- **Hook into reaktiv**: a level Monitor can register as an `Effect` on a `Signal` — when the Signal changes, tally `(env.now, new_value)` automatically.

```
Monitor
├── _t : array.array('d')        # timestamps
├── _x : array.array('?')        # values (typed)
├── tally(value)                 # called on each change
├── mean(ex0=False)              # time-weighted if level
├── std(ex0=False)
├── percentile(q)
├── histogram(bins)
└── print_statistics()
```

---

### 1.3 Queue — augment, not replace

hsim's reaktiv-backed `Queue` handles conditional unblocking better than salabim's linked-list queue. **Augment** it:

| Addition | Source |
|---|---|
| `length` — level Monitor auto-tallied on every put/get | salabim |
| `length_of_stay` — non-level Monitor, tally on get with `now - enter_time` | salabim |
| `arrival_rate` / `departure_rate` — rolling window | salabim |
| `animate()` hook — returns serializable state dict for web rendering | adapted |
| `print_statistics()` — delegates to two Monitors | salabim |

---

### 1.4 Resource (new class)

Add `Resource` to `hsim/core/des/` alongside existing blocks. Wraps two Queues + four level Monitors.

```
Resource(capacity=1, preemptive=False, anonymous=False)
├── requesters : Queue           # waiting to claim
├── claimers   : Queue           # currently holding
├── capacity          : Monitor (level)
├── available_quantity: Monitor (level)
├── claimed_quantity  : Monitor (level)
└── occupancy         : Monitor (level)  0–1 float
```

Key features to port:
- `request(quantity, priority, timeout)` — enters requesters queue, activates FSM transition when honoured
- `release(quantity)` — removes from claimers, re-honours next requester
- `preemptive=True` — bump lower-priority claimant with `interrupted` status
- `anonymous=True` — tank/continuous-level resource (fuel, WIP buffer level)

---

### 1.5 Trajectory / Movement — for conveyors and AGVs

Extract into `hsim/core/des/trajectory.py`. **Zero animation dependency** — pure kinematics.

```
_Movement(length, vmax, v0, v1, acc, dec)
└── l_at_t(t) → float            # position along path at time t
    # handles acc ramp, cruise, dec ramp with physics

TrajectoryPolygon(polygon, vmax, acc, dec, spline=None)
├── x(t), y(t)                   # world position at time t
├── angle(t)                     # heading
└── duration                     # total travel time

TrajectoryCircle(center, radius, vmax, ...)
TrajectoryMerged([traj1, traj2, ...])    # chain trajectories
```

Integration with hsim:
- Conveyor modeled as `TrajectoryPolygon` + `hold(duration=traj.duration)`
- AGV modeled as component that follows trajectory, queries `x(t)` / `y(t)` for animation state
- For **continuous** tracking: reaktiv `ComputeSignal(lambda: traj.x(env.now))` — position becomes a reactive signal, cheap to subscribe to for animation without any per-tick event

---

### 1.6 Distribution ergonomics

Add `hsim/core/utils/distributions.py` with named wrappers over scipy/numpy:

```python
Exponential(mean=5)          # .sample()  .mean()
Normal(mean=10, std=2)       # Bounded(Normal(...), lower=0)
Uniform(lower=1, upper=5)
Triangular(low, mid, high)
Erlang(k, mean)
Pdf(values, probabilities)   # discrete
```

Consistent interface:
- `dist()` or `dist.sample()` → one sample
- `dist.mean()` → analytical mean where available
- All wrappers callable so they plug directly into salabim-style `iat=Exponential(5)` patterns.

---

### 1.7 ComponentGenerator enhancements

Augment existing `Generator` in `pymulate.py`:

| Feature | Rationale |
|---|---|
| `moments=[t1, t2, ...]` — exact scheduled arrivals | Deterministic scenario injection |
| `equidistant=True` — N arrivals spread evenly in `[at, till]` | Warm-up / batch loading |
| `at_end=callback` — hook when generation wave ends | Chained scenario phases |
| `disturbance=dist` — jitter on top of IAT | Realistic inter-arrival noise |

---

### 1.8 Animation bridge (concept, not tkinter)

Salabim's `DynamicClass` pattern — attributes as `f(t)` — maps cleanly to a `animation_state()` protocol:

```python
class AnimationMixin:
    def animation_state(self, t: float) -> dict:
        """Return serializable state dict for web renderer."""
        ...
```

`AnimateMonitor`-equivalent: a Monitor's `_t` / `_x` arrays are directly Plotly-compatible — `go.Scatter(x=mon._t, y=mon._x)`.

`AnimateQueue`: push queue contents as a JSON list over WebSocket from the Flask backend.

---

## 2. What NOT to borrow

| salabim feature | Reason to skip |
|---|---|
| Greenlet execution model | FSM callbacks are structurally cleaner and testable |
| `State` class (waiters queue) | reaktiv `Signal` + FSM already expresses this more powerfully |
| tkinter / OpenGL 3D animation | Not aligned with Flask/web stack |
| `_set_name` / `_nameserialize*` registry | Logging config covers the use case |
| Pythonista / pyodide compat | Not relevant |
| `_StatusMonitor` / `_ModeMonitor` | Internal trace machinery; Monitor itself is the value |

---

## 3. Implementation phases

| Phase | Deliverable | File(s) | Status |
|---|---|---|---|
| **1** | `Monitor` class with level/non-level, `array.array` backing, stats API | `hsim/core/stats/monitor.py` | ✅ Done |
| **2** | Queue augmented with `length` + `length_of_stay` Monitors | `hsim/core/agent/q.py` | ✅ Done |
| **3** | `Resource` class with requesters/claimers queues + 4 Monitors | `hsim/core/des/resources.py` | ✅ Done |
| **4** | Scheduler `urgent` flag + `cap_now` guard + `standby` list | `hsim/core/core/env.py` | ✨ Simplified (priorities sufficient) |
| **5** | `TrajectoryPolygon`, `_Movement`, `TrajectoryMerged`, `TrajectoryCircle` | `hsim/core/des/trajectory.py` | 🔄 In Progress |
| **6** | Distribution wrappers | `hsim/core/utils/distributions.py` | ⏳ Planned |
| **7** | `ComponentGenerator` enhancements | `hsim/core/des/pymulate.py` | ⏳ Planned |
| **8** | Animation: `animation_state()` mixin + Plotly export | `hsim/core/stats/animation.py` | ⏳ Planned |

---

## 3.5 Animation strategy (web-first)

```
┌─────────────────────────────────────────────────────┐
│ Simulation (hsim)                                   │
├─────────────────────────────────────────────────────┤
│ • Monitor._t, Monitor._x arrays (time-series data)  │
│ • AGV.animation_state(t) → { x, y, z, rotation }   │
│ • Queue items + positions                           │
└────────────┬────────────────────────────────────────┘
             │ JSON export via Flask
             ↓
┌─────────────────────────────────────────────────────┐
│ Web Renderer (Plotly/Three.js)                      │
├─────────────────────────────────────────────────────┤
│ • Line charts: Monitor time-series                  │
│ • 3D canvas: animated positions via trajectory.x(t) │
│ • Timeline scrubber: frame-by-frame playback        │
└─────────────────────────────────────────────────────┘
```

**Key insight**: No per-tick animation event. `trajectory.x(t)` is purely mathematical — evaluate on demand from stored simulation times.

**Monitor visualization**: `go.Scatter(x=monitor._t, y=monitor._x, mode='lines')` — direct Plotly feed.

**Trajectory preview**: Plot all waypoints and circle segments; highlight current location based on current time.

---

## 4. reaktiv — where it belongs and where it doesn't

### 4.1 Benchmark results (100k iterations, this machine)

| Approach | ops/s | relative |
|---|---|---|
| raw `list` callbacks (`__slots__`) | 8.1 M/s | 1× (baseline) |
| minimal `Observable` class | 5.1 M/s | 0.63× |
| reaktiv `Signal.set` + 1 Effect | 0.13 M/s | **~62× slower** |
| reaktiv 2-level `ComputeSignal` + 1 Effect | 0.06 M/s | **~135× slower** |
| `ContextVar.get()` alone | 23 M/s | — (overhead component) |
| `array.array.append` ×2 | 5.0 M/s | — (Monitor tally) |

The overhead is structural: every `Signal.set()` calls `ContextVar.get()` for dependency tracking, traverses the edge linked list, and synchronously flushes all pending effects. The patches in `obs.py` (bypassing some calls when no active consumer) reduce it from ~900ms to ~800ms — still 62× slower than raw callbacks.

### 4.2 Where reaktiv is the right choice

reaktiv shines when **automatic dependency tracking** eliminates manual wiring that would be error-prone:

1. **`ConditionedEvent`** — waiting until a computed boolean expression across multiple Signals becomes `True` (e.g. `queue.size < capacity AND machine.status == idle`). The automatic edge tracking means no manual subscribe/unsubscribe bookkeeping. This is exactly its Angular Signals / SolidJS design goal.

2. **Continuous position signals for animation** — `ComputeSignal(lambda: trajectory.x(env.now))` lets animation consumers subscribe without the simulation having to push updates. Pull-on-render semantics.

3. **Complex derived conditions** — multi-source computed guards where the dependency graph changes dynamically.

### 4.3 Where reaktiv is the wrong choice — and what to use instead

| Current use | Problem | Better approach |
|---|---|---|
| `ObservableVariable` backing `queue.length`, `queue.capacity` | Every queue operation (~4M per big simulation run) pays the 62× overhead | Plain Python `__slots__` attribute + direct call to `Monitor.tally()` |
| `_SystemMonitor`-like level tracking | Monitoring is write-once-per-event, never needs graph traversal | `array.array` + time stamp, read stats at end |
| `queue.length` as a `Signal` for `capacity_condition` | The condition is binary and the Signal side is a single integer — overkill | `if len(queue) < capacity: fire_event()` in `_put()` / `get()` |
| Simple threshold conditions in FSM transitions | Polling overhead, no true fan-out | Direct callback in transition `on_transition` |

### 4.4 Proposed layered architecture

```
Layer 3 — Reactive expressions (keep reaktiv)
  ConditionedEvent, multi-source computed conditions, animation signals
  
Layer 2 — Observable notification (roll minimal __slots__ Observable)
  Queue length change → notify Monitor.tally()
  Resource capacity change → notify downstream requesters
  ~5–8× faster than reaktiv
  
Layer 1 — Pure state (plain Python)
  Monitor._t, Monitor._x arrays
  Scheduler FEL (heapq)
  FSM state transitions
```

### 4.5 Minimal `Observable` design (Layer 2 replacement)

```python
class Observable:
    """Lightweight observable value. No graph tracking, no ContextVar overhead.
    Subscribers are callbacks called synchronously on set()."""
    __slots__ = ('_value', '_observers')
    
    def __init__(self, value):
        self._value = value
        self._observers: list[Callable] = []
    
    def get(self) -> Any:
        return self._value
    
    def set(self, value) -> None:
        self._value = value
        for cb in self._observers:
            cb(value)
    
    def observe(self, cb: Callable) -> None:
        self._observers.append(cb)
    
    def unobserve(self, cb: Callable) -> None:
        self._observers.remove(cb)
    
    # Operator overloads for ComputeSignal-compatible expressions
    # delegate to a reaktiv Signal proxy ONLY when an expression is built
    def __lt__(self, other): return ObservableExpr(operator.lt, self, other)
    def __le__(self, other): return ObservableExpr(operator.le, self, other)
    # ...etc
```

`ObservableExpr` (only created when you write `queue.length < queue.capacity`) wraps into a reaktiv `ComputeSignal` at that point — paying the cost only for the conditions that need it, not for every tally.

### 4.6 Migration strategy

1. `ObservableVariable` in `obs.py` acquires a **fast path**: if no reactive graph is active (`graph.active_consumer.get() is None`) AND no `Effect` subscribers exist, bypass reaktiv entirely and call observers directly. This is already partially done by the `_patched_signal_get` in `obs.py`.
2. Long-term: introduce the `Observable` class above as `hsim.core.core.obs.Observable`, make `ObservableVariable` inherit from it, keep reaktiv `Signal` as a mixin only for expression building.
3. Audit all `Effect(lambda: ...)` usages — replace with direct `observe()` callbacks where the dependency is static and known at construction time.

### 4.7 Alternatives evaluated

| Library | Speed (relative) | Fit for DES |
|---|---|---|
| **reaktiv 0.19** | 1× (current baseline) | Good for reactive expressions; too slow for hot path |
| **traitlets** (Jupyter) | ~10–15× faster than reaktiv | Mature, but designed for UI widgets, carries IPython baggage |
| **param** (HoloViz) | ~8–12× faster than reaktiv | Numerical parameters focus, closest to what we need, but adds HoloViz dependency |
| **custom `Observable`** (proposed) | ~62× faster than reaktiv | Zero deps, tailored to DES hot path; loses auto dependency tracking |
| **reaktiv (scoped)** | 1× for reactive, 62× loss for non-reactive | Keep for `ConditionedEvent` only |
| **salabim `State`** (waiters queue pattern) | N/A | Simpler model but requires greenlet/yieldless execution |

**Recommendation: scoped reaktiv** — keep it for `ConditionedEvent` and multi-source computed expressions only; replace `ObservableVariable` in the hot path (monitor tallying, queue length tracking) with the custom `Observable`.

---

## 5. Continuous dynamics and conveyors

For conveyors and transportation in general, two sub-problems:

### 5.1 Travel time (discrete, most common)
Model conveyor as a `hold(duration=length/speed)`. Entity enters at t, exits at t+duration. No continuous integration needed.

### 5.2 Live position tracking (continuous, for animation / collision)
Use `TrajectoryPolygon.l_at_t(env.now - entry_time)` as a pure function query. For animation: a reaktiv `ComputeSignal` that reads `env.now` — pulling position on demand.

For true continuous dynamics (speed varies, e.g. variable-speed conveyor or vehicle following a speed profile), integrate with scipy ODE solver (`solve_ivp`) at event boundaries, storing the solution as a callable, exactly like salabim's `_Movement.l_at_t`.

### 5.3 Reactive continuous variables
Where a continuous variable must trigger discrete events (e.g. buffer level reaches threshold), use:
- A `Monitor`-recorded continuous trajectory
- A binary `Signal` derived via `ComputeSignal` that fires when threshold crossed
- The `ConditionedEvent` subscribes to that Signal

This keeps the DES scheduler in control; no sub-step integration needed.

---

## 6. Open questions

1. **Monitor scope**: should Monitor be env-global (like salabim, where `env._nameserializeMonitor` tracks all) or locally owned per Queue/Resource? Recommendation: locally owned, collected into a `SimulationReport` at end of run.
2. **`urgent` scheduler flag**: do existing test cases need updating to respect the new tuple sort key?
3. **Resource vs Server**: `Resource` is stateless capacity; `Server` in hsim is stateful (FSM). Should `Server` inherit from `Resource` (for capacity tracking) or compose it?
4. **Web animation protocol**: WebSocket push vs polling endpoint for the GSOM dashboard?
