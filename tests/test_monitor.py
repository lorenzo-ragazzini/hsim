"""Tests for Monitor classes."""

import unittest
import math
from hsim.core.stats.monitor import LevelMonitor, NonLevelMonitor


class TestLevelMonitor(unittest.TestCase):
    """Test LevelMonitor for time-weighted statistics."""
    
    def test_basic_creation(self):
        """Test monitor creation and basic properties."""
        m = LevelMonitor("test")
        self.assertEqual(m.name, "test")
        self.assertEqual(m.number_of_entries(), 0)
        self.assertEqual(m.mean(), 0.0)
    
    def test_single_value(self):
        """Test monitor with single value."""
        m = LevelMonitor("test")
        m.tally(0.0, 10.0)
        self.assertEqual(m.number_of_entries(), 1)
        self.assertEqual(m.mean(), 10.0)
    
    def test_time_weighted_mean_simple(self):
        """Test time-weighted mean calculation.
        
        Timeline:
        - [0, 5): value=10
        - [5, 10): value=20
        Total: (10*5 + 20*5) / 10 = 15
        """
        m = LevelMonitor("test")
        m.tally(0.0, 10.0)
        m.tally(5.0, 20.0)
        m.tally(10.0, 30.0)
        
        expected_mean = (10*5 + 20*5) / 10
        self.assertAlmostEqual(m.mean(), expected_mean)
    
    def test_time_weighted_mean_weighted(self):
        """Test time-weighted mean with different durations.
        
        Timeline:
        - [0, 2): value=5
        - [2, 8): value=15
        Total: (5*2 + 15*6) / 8 = (10 + 90) / 8 = 12.5
        """
        m = LevelMonitor("test")
        m.tally(0.0, 5.0)
        m.tally(2.0, 15.0)
        m.tally(8.0, 25.0)
        
        expected_mean = (5*2 + 15*6) / 8
        self.assertAlmostEqual(m.mean(), expected_mean)
    
    def test_reset(self):
        """Test monitor reset."""
        m = LevelMonitor("test")
        m.tally(0.0, 10.0)
        m.tally(5.0, 20.0)
        
        self.assertEqual(m.number_of_entries(), 2)
        m.reset()
        self.assertEqual(m.number_of_entries(), 0)
        self.assertEqual(m.mean(), 0.0)


class TestNonLevelMonitor(unittest.TestCase):
    """Test NonLevelMonitor for sample statistics."""
    
    def test_basic_creation(self):
        """Test monitor creation."""
        m = NonLevelMonitor("test")
        self.assertEqual(m.name, "test")
        self.assertEqual(m.number_of_entries(), 0)
        self.assertEqual(m.mean(), 0.0)
        self.assertEqual(m.variance(), 0.0)
    
    def test_single_sample(self):
        """Test monitor with single sample."""
        m = NonLevelMonitor("test")
        m.tally(5.0)
        
        self.assertEqual(m.number_of_entries(), 1)
        self.assertEqual(m.mean(), 5.0)
        self.assertEqual(m.minimum(), 5.0)
        self.assertEqual(m.maximum(), 5.0)
    
    def test_mean_calculation(self):
        """Test mean calculation with multiple samples."""
        m = NonLevelMonitor("test")
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for v in values:
            m.tally(v)
        
        expected_mean = sum(values) / len(values)
        self.assertAlmostEqual(m.mean(), expected_mean)
        self.assertEqual(m.number_of_entries(), 5)
    
    def test_variance_welford(self):
        """Test variance calculation using Welford's algorithm.
        
        Sample: [1, 2, 3, 4, 5]
        Mean = 3.0
        Sample variance = ((1-3)^2 + (2-3)^2 + (3-3)^2 + (4-3)^2 + (5-3)^2) / (n-1)
                       = (4 + 1 + 0 + 1 + 4) / 4 = 10 / 4 = 2.5
        """
        m = NonLevelMonitor("test")
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for v in values:
            m.tally(v)
        
        expected_variance = 2.5
        self.assertAlmostEqual(m.variance(), expected_variance)
    
    def test_std_dev(self):
        """Test standard deviation."""
        m = NonLevelMonitor("test")
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for v in values:
            m.tally(v)
        
        expected_std = math.sqrt(2.5)
        self.assertAlmostEqual(m.std_dev(), expected_std)
    
    def test_min_max(self):
        """Test minimum and maximum tracking."""
        m = NonLevelMonitor("test")
        values = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
        for v in values:
            m.tally(v)
        
        self.assertEqual(m.minimum(), 1.0)
        self.assertEqual(m.maximum(), 9.0)
    
    def test_reset(self):
        """Test monitor reset."""
        m = NonLevelMonitor("test")
        for v in [1.0, 2.0, 3.0]:
            m.tally(v)
        
        self.assertEqual(m.number_of_entries(), 3)
        m.reset()
        self.assertEqual(m.number_of_entries(), 0)
        self.assertEqual(m.mean(), 0.0)
        self.assertEqual(m.variance(), 0.0)


if __name__ == "__main__":
    unittest.main()
