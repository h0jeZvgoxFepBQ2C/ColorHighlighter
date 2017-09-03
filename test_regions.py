"""Tests for regions.NormalizedRegion."""

try:
    from .st_helper import running_in_st
except ValueError:
    from st_helper import running_in_st


if not running_in_st():

    import unittest

    from .regions import NormalizedRegion, intersects

    class IntersectTest(unittest.TestCase):
        """Tests for intersects."""

        def test_intersects(self):
            """Test all cases."""
            region = NormalizedRegion(4, 7)
            self.assertFalse(intersects(NormalizedRegion(1, 3), region))
            self.assertFalse(intersects(NormalizedRegion(2, 4), region))
            self.assertTrue(intersects(NormalizedRegion(4, 4), region))
            self.assertTrue(intersects(NormalizedRegion(3, 5), region))
            self.assertTrue(intersects(NormalizedRegion(4, 7), region))
            self.assertTrue(intersects(NormalizedRegion(5, 8), region))
            self.assertTrue(intersects(NormalizedRegion(7, 7), region))
            self.assertFalse(intersects(NormalizedRegion(7, 9), region))
            self.assertFalse(intersects(NormalizedRegion(8, 10), region))
