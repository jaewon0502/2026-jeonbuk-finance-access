"""Geometry, classification and directed additive-pool invariants."""

import sys
import unittest
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run_spatial_validation as spatial
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely import transform


class SpatialValidationTests(unittest.TestCase):
    def as_wgs84(self, projected):
        return mapping(transform(projected, spatial.TO_WGS84, interleaved=False))

    def test_full_multipolygon_centroid_uses_component_area(self):
        small = Polygon([(950000, 1800000), (951000, 1800000), (951000, 1801000), (950000, 1801000)])
        large = Polygon([(954000, 1800000), (956000, 1800000), (956000, 1802000), (954000, 1802000)])
        geometry = MultiPolygon([small, large])
        lon, lat, inside, area = spatial.projected_centroid(self.as_wgs84(geometry))
        x, y = spatial.TO_METERS(lon, lat)
        self.assertAlmostEqual(x, geometry.centroid.x, places=5)
        self.assertAlmostEqual(y, geometry.centroid.y, places=5)
        self.assertAlmostEqual(area, 5.0, places=6)
        self.assertTrue(inside)

    def test_hole_area_is_subtracted_regardless_of_ring_orientation(self):
        outer = [(950000, 1800000), (954000, 1800000), (954000, 1804000), (950000, 1804000)]
        hole = [(950500, 1800500), (951500, 1800500), (951500, 1801500), (950500, 1801500)]
        geometry = Polygon(outer, [hole])
        lon, lat, inside, area = spatial.projected_centroid(self.as_wgs84(geometry))
        x, y = spatial.TO_METERS(lon, lat)
        self.assertAlmostEqual(x, geometry.centroid.x, places=5)
        self.assertAlmostEqual(y, geometry.centroid.y, places=5)
        self.assertAlmostEqual(area, 15.0, places=6)
        self.assertTrue(inside)

    def test_centroid_inside_hole_is_flagged_outside(self):
        outer = [(950000, 1800000), (954000, 1800000), (954000, 1804000), (950000, 1804000)]
        hole = [(951000, 1801000), (953000, 1801000), (953000, 1803000), (951000, 1803000)]
        _, _, inside, _ = spatial.projected_centroid(self.as_wgs84(Polygon(outer, [hole])))
        self.assertFalse(inside)

    def test_disconnected_equal_islands_centroid_is_not_moved_inside(self):
        left = Polygon([(950000, 1800000), (951000, 1800000), (951000, 1801000), (950000, 1801000)])
        right = Polygon([(954000, 1800000), (955000, 1800000), (955000, 1801000), (954000, 1801000)])
        lon, lat, inside, _ = spatial.projected_centroid(self.as_wgs84(MultiPolygon([left, right])))
        x, _ = spatial.TO_METERS(lon, lat)
        self.assertAlmostEqual(x, 952500, places=5)
        self.assertFalse(inside)

    def test_thresholds_use_unrounded_strict_inequality(self):
        self.assertEqual(spatial.category(3.0), "within_threshold")
        self.assertEqual(spatial.category(3.00001), "P2")
        self.assertEqual(spatial.category(5.0), "P2")
        self.assertEqual(spatial.category(5.00001), "P1")
        self.assertEqual(spatial.category(""), "unrouted")

    def test_outside_or_fallback_origins_not_route_targets(self):
        row = {"road_km": 7.0, "origin_inside_boundary": "N", "road_distance_primary": "Y"}
        self.assertEqual(spatial.route_category(row), "outside_origin")
        row.update(origin_inside_boundary="Y", road_distance_primary="N")
        self.assertEqual(spatial.route_category(row), "quality_deferred")

    def test_adding_outlet_preserves_directed_distance_monotonicity(self):
        # Reversed edges correspond to original path 0 -> 1 -> 2.
        offsets = array("Q", [0, 0, 1, 2])
        neighbors = array("I", [0, 1])
        weights = array("f", [2.0, 3.0])
        old, _, _, _ = spatial.road.multi_source_to_targets(offsets, neighbors, weights, [(2, 0.2, 0)])
        new, sources, _, _ = spatial.road.multi_source_to_targets(offsets, neighbors, weights, [(2, 0.2, 0), (1, 0.1, 1)])
        for left, right in zip(old, new):
            self.assertLessEqual(right, left)
        self.assertAlmostEqual(old[0], 5.2)
        self.assertAlmostEqual(new[0], 2.1)
        self.assertEqual(sources[0], 1)
        self.assertAlmostEqual(new[2], 0.2)

    def test_additive_pool_rejects_coordinate_or_status_changes(self):
        old = [{"outlet_id": "A", "lat": 35.0, "lon": 127.0, "finance_open": "Y"}]
        spatial.validate_additive_pool(old, old + [{"outlet_id": "B"}])
        with self.assertRaisesRegex(ValueError, "not additive"):
            spatial.validate_additive_pool(old, [{**old[0], "lat": 35.1}])


if __name__ == "__main__":
    unittest.main()
