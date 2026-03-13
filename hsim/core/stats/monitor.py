"""Monitor classes for tracking statistics in DES simulations."""

from array import array
import math
from typing import List, Optional


class LevelMonitor:
    """Monitors a level (piecewise-constant) signal and maintains time-weighted statistics.
    
    Tracks a value that changes over time and maintains:
    - Time-weighted mean
    - Time-weighted variance and std dev
    - Sample percentiles
    """
    
    def __init__(self, name: str = ""):
        """Initialize level monitor.
        
        Args:
            name: Monitor name for identification
        """
        self.name = name
        self._values = array('d')  # Values recorded
        self._timestamps = array('d')  # Timestamps when values changed
        self._last_time = 0.0
        
    def tally(self, time: float, value: float):
        """Record a value change at a given time.
        
        Args:
            time: Simulation time of the change
            value: New value
        """
        self._timestamps.append(time)
        self._values.append(value)
        self._last_time = time
    
    def mean(self) -> float:
        """Calculate time-weighted mean."""
        if not self._timestamps:
            return 0.0
        if len(self._timestamps) == 1:
            return self._values[0]
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for i in range(len(self._timestamps) - 1):
            duration = self._timestamps[i + 1] - self._timestamps[i]
            value = self._values[i]
            total_weight += duration
            weighted_sum += value * duration
        
        # Add final period (from last recorded time to current time)
        if total_weight > 0:
            return weighted_sum / total_weight
        return self._values[-1] if self._values else 0.0
    
    def number_of_entries(self) -> int:
        """Return number of recorded changes."""
        return len(self._timestamps)
    
    def reset(self):
        """Clear all recorded data."""
        self._values = array('d')
        self._timestamps = array('d')
        self._last_time = 0.0


class NonLevelMonitor:
    """Monitors discrete samples and maintains statistics.
    
    Uses Welford's algorithm for online computation of mean and variance.
    Tracks:
    - Sample mean
    - Sample variance and std dev
    - Min/max values
    - Number of observations
    """
    
    def __init__(self, name: str = ""):
        """Initialize non-level monitor.
        
        Args:
            name: Monitor name for identification
        """
        self.name = name
        self._count = 0
        self._mean = 0.0
        self._m2 = 0.0  # For variance calculation (Welford)
        self._min = float('inf')
        self._max = float('-inf')
        self._values = array('d')  # All recorded values
    
    def tally(self, value: float):
        """Record a sample observation.
        
        Uses Welford's online algorithm for variance:
        https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
        
        Args:
            value: Observed value
        """
        self._count += 1
        self._values.append(value)
        
        # Welford's algorithm
        delta = value - self._mean
        self._mean += delta / self._count
        delta2 = value - self._mean
        self._m2 += delta * delta2
        
        # Track min/max
        self._min = min(self._min, value)
        self._max = max(self._max, value)
    
    def mean(self) -> float:
        """Return sample mean."""
        return self._mean if self._count > 0 else 0.0
    
    def variance(self) -> float:
        """Return sample variance."""
        if self._count < 2:
            return 0.0
        return self._m2 / (self._count - 1)
    
    def std_dev(self) -> float:
        """Return sample standard deviation."""
        return math.sqrt(self.variance())
    
    def minimum(self) -> float:
        """Return minimum observed value."""
        return self._min if self._min != float('inf') else 0.0
    
    def maximum(self) -> float:
        """Return maximum observed value."""
        return self._max if self._max != float('-inf') else 0.0
    
    def number_of_entries(self) -> int:
        """Return number of observations."""
        return self._count
    
    def reset(self):
        """Clear all recorded data."""
        self._count = 0
        self._mean = 0.0
        self._m2 = 0.0
        self._min = float('inf')
        self._max = float('-inf')
        self._values = array('d')
