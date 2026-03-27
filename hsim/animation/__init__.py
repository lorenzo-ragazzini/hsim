"""
hsim.animation — salabim-backed animation utilities for HSim.

Requires HSimEnvironment (not plain Environment).

Quick start:
    env = HSimEnvironment()
    env.animation_parameters(width=1200, height=700, background_color="20%gray")
    # ... attach AnimateQueueLength, AnimateFSMState, etc. ...
    env.run(until=200)
"""
try:
    import salabim as _sim
    from salabim import (
        AnimateText,
        AnimateRectangle,
        AnimateMonitor,
        AnimateQueue,
        Animate,
    )
    from hsim.animation.helpers import AnimateQueueLength, AnimateFSMState
    _AVAILABLE = True
except ImportError as _e:
    _AVAILABLE = False
    def _missing(*a, **kw):
        raise ImportError("salabim animation requires salabim") from _e
    AnimateText = AnimateRectangle = AnimateMonitor = AnimateQueue = _missing
    Animate = AnimateQueueLength = AnimateFSMState = _missing