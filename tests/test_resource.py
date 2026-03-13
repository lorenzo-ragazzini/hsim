"""Tests for Resource class."""

import unittest
from hsim.core.des.resources import Resource
from hsim.core.core.env import Environment


class TestResource(unittest.TestCase):
    """Test Resource for capacity-managed request/release semantics."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.env = Environment()
    
    def test_resource_creation(self):
        """Test resource creation with default capacity."""
        r = Resource("test_resource", capacity=5, env=self.env)
        
        self.assertEqual(r.name, "test_resource")
        self.assertEqual(r.capacity, 5)
        self.assertEqual(r.available(), 5)
        self.assertEqual(r.claimed(), 0)
        self.assertEqual(r.occupancy(), 0)
    
    def test_request_available_units(self):
        """Test requesting available units."""
        r = Resource("test", capacity=10, env=self.env)
        
        # Request 3 units
        granted = r.request("entity_1", quantity=3)
        
        self.assertTrue(granted)
        self.assertEqual(r.available(), 7)
        self.assertEqual(r.claimed(), 3)
        self.assertEqual(r.occupancy(), 0)
    
    def test_request_all_units(self):
        """Test requesting all available units."""
        r = Resource("test", capacity=5, env=self.env)
        
        granted = r.request("entity_1", quantity=5)
        
        self.assertTrue(granted)
        self.assertEqual(r.available(), 0)
        self.assertEqual(r.claimed(), 5)
    
    def test_request_exceeds_capacity(self):
        """Test requesting more units than available."""
        r = Resource("test", capacity=5, env=self.env)
        
        # First request takes 3, then try to request 4 (should queue)
        r.request("entity_1", quantity=3)
        granted = r.request("entity_2", quantity=4)
        
        self.assertFalse(granted)  # Not immediately granted
        self.assertEqual(r.available(), 2)  # Still have 2
        self.assertEqual(r.claimed(), 3)   # Only 3 claimed
        self.assertEqual(r.occupancy(), 1)  # 1 queued
    
    def test_release_and_fulfill_queue(self):
        """Test that releasing units fulfills queued requests."""
        r = Resource("test", capacity=5, env=self.env)
        
        # Allocate 3, leaving 2 available
        r.request("e1", quantity=3)
        
        # Request 2 (should be granted since exactly 2 available)
        granted = r.request("e2", quantity=2)
        self.assertTrue(granted)  # Now all 5 units are claimed
        
        # Request 2 more (should be queued)
        granted = r.request("e3", quantity=2)
        self.assertFalse(granted)
        
        self.assertEqual(r.occupancy(), 1)
        
        # Release 1 unit from first requester
        r.release("e1", quantity=1)
        
        # After release: e1 has 2, e2 has 2, e3 is still waiting for 2
        # Available = 1, claimed = 4
        self.assertEqual(r.available(), 1)
        self.assertEqual(r.claimed(), 4)
        self.assertEqual(r.occupancy(), 1)
    
    def test_multiple_releases(self):
        """Test multiple sequential releases."""
        r = Resource("test", capacity=10, env=self.env)
        
        # Allocate 5
        r.request("e1", quantity=5)
        self.assertEqual(r.claimed(), 5)
        
        # Release 2
        r.release("e1", quantity=2)
        self.assertEqual(r.available(), 7)
        self.assertEqual(r.claimed(), 3)
        
        # Release more
        r.release("e1", quantity=3)
        self.assertEqual(r.available(), 10)
        self.assertEqual(r.claimed(), 0)
    
    def test_monitoring_available_changes(self):
        """Test that available monitor tracks changes correctly."""
        r = Resource("test", capacity=5, env=self.env)
        
        # Initial state
        self.assertEqual(r.available_monitor.number_of_entries(), 1)
        
        # Request units
        r.request("e1", quantity=2)
        self.assertEqual(r.available_monitor.number_of_entries(), 2)
        
        # Release units
        r.release("e1", quantity=2)
        self.assertEqual(r.available_monitor.number_of_entries(), 3)
    
    def test_monitoring_claimed_changes(self):
        """Test that claimed monitor tracks changes correctly."""
        r = Resource("test", capacity=5, env=self.env)
        
        # Initial state
        initial_entries = r.claimed_monitor.number_of_entries()
        self.assertEqual(initial_entries, 1)
        
        # Request units - should add monitor entry
        r.request("e1", quantity=3)
        self.assertEqual(r.claimed_monitor.number_of_entries(), 2)
        
        # Release units - should add another monitor entry
        r.release("e1", quantity=3)  
        self.assertEqual(r.claimed_monitor.number_of_entries(), 3)
    
    def test_single_unit_resource(self):
        """Test resource with capacity of 1 (like a mutex)."""
        r = Resource("mutex", capacity=1, env=self.env)
        
        # Lock it
        granted = r.request("e1", quantity=1)
        self.assertTrue(granted)
        self.assertEqual(r.available(), 0)
        
        # Try to lock again (should queue)
        granted = r.request("e2", quantity=1)
        self.assertFalse(granted)
        self.assertEqual(r.occupancy(), 1)
        
        # Unlock
        r.release("e1", quantity=1)
        
        # Now e2 should be satisfied
        self.assertEqual(r.available(), 0)  # All claimed by e2
        self.assertEqual(r.occupancy(), 0)  # Queue empty


if __name__ == "__main__":
    unittest.main()
