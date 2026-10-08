"""
Runs a model on a sample of the real rental catalog, and checks how that catalog is cleaned.
"""

import math
import unittest

import pandas as pd

from src.core.listings import (
    KM_PER_DEGREE_LAT,
    KM_PER_DEGREE_LON,
    MAP_UNITS_PER_KM,
    MAX_KM_FROM_CITY,
    RAW_REAL_CATALOG,
    REAL_CATALOG,
    _convex_hull,
    _km_from_city_median,
    _map_frame,
    _to_map,
    clean_real_catalog,
    load_instance,
    load_real_catalog,
)
from src.models.model_7 import build_model_m7
from src.solvers.engine import solve_model


class RealDatasetTest(unittest.TestCase):
    def test_m7_solves_one_neighborhood(self):
        data = load_instance("real", "m7", num_properties=5, random_seed=42,
                             city="São Paulo", neighborhood="Moema")
        catalog = load_real_catalog(REAL_CATALOG, city="São Paulo", neighborhood="Moema")
        catalog_ids = set(catalog["id"].astype(str))

        self.assertEqual(data["num_nodes"], 6)
        self.assertEqual(len(data["listings"]), 5)
        self.assertGreater(len(catalog), 5)
        self.assertEqual(len({listing["id"] for listing in data["listings"]}), 5)
        for listing in data["listings"]:
            self.assertIn(listing["id"], catalog_ids)
            self.assertEqual(listing["city"], "São Paulo")
            self.assertEqual(listing["district"], "Moema")
            self.assertGreaterEqual(data["service_times"][listing["node"]], 30)
            self.assertLessEqual(data["service_times"][listing["node"]], 90)

        self._assert_edges_follow_listing_coordinates(data)

        solved_model, metrics = solve_model(build_model_m7(data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
        self.assertEqual(metrics["solver_status"], "ok")
        self.assertEqual(metrics["termination_condition"], "optimal")
        self.assertIsNotNone(solved_model)

    def _assert_edges_follow_listing_coordinates(self, data):
        """Each edge is the straight-line separation of listing.address.point.lat / lon."""
        listings = data["listings"]
        origin_lat = sum(listing["lat"] for listing in listings) / len(listings)
        origin_lon = sum(listing["lon"] for listing in listings) / len(listings)
        km_per_degree_lon = KM_PER_DEGREE_LON * math.cos(math.radians(origin_lat))
        for listing in listings:
            east_km = (listing["lon"] - origin_lon) * km_per_degree_lon
            north_km = (listing["lat"] - origin_lat) * KM_PER_DEGREE_LAT
            expected = [round(50.0 + east_km * MAP_UNITS_PER_KM, 2),
                        round(50.0 + north_km * MAP_UNITS_PER_KM, 2)]
            self.assertEqual(data["coordinates"][listing["node"]], expected)

        for left in listings:
            for right in listings:
                if left["node"] == right["node"]:
                    continue
                start = data["coordinates"][left["node"]]
                end = data["coordinates"][right["node"]]
                separation = round(math.hypot(start[0] - end[0], start[1] - end[1]), 2)
                self.assertEqual(data["distance_matrix"][left["node"]][right["node"]], separation)
        self.assertGreater(max(max(row) for row in data["distance_matrix"]), 0)

    def test_real_instance_requires_a_neighborhood(self):
        with self.assertRaises(ValueError):
            load_instance("real", "m7", city="São Paulo")

    def test_broker_homes_lie_inside_the_city(self):
        data = load_instance("real", "m7", num_properties=5, random_seed=42,
                             city="São Paulo", neighborhood="Moema")
        origin_lat, origin_lon, km_per_degree_lon = _map_frame(
            [listing["lat"] for listing in data["listings"]],
            [listing["lon"] for listing in data["listings"]],
        )

        def polygon_of(latitudes, longitudes):
            projected = [_to_map(lat, lon, origin_lat, origin_lon, km_per_degree_lon)
                         for lat, lon in zip(latitudes, longitudes)]
            return [list(point) for point in _convex_hull([(point[0], point[1]) for point in projected])]

        city_catalog = load_real_catalog(REAL_CATALOG, city="São Paulo")
        city = polygon_of(city_catalog["lat"], city_catalog["lon"])
        moema_catalog = load_real_catalog(REAL_CATALOG, city="São Paulo", neighborhood="Moema")
        moema = polygon_of(moema_catalog["lat"], moema_catalog["lon"])

        self.assertEqual(len(data["home_coordinates"]), 3)
        self.assertGreater(len(city), 2)
        for home in data["home_coordinates"]:
            self.assertTrue(self._inside_polygon(home, city))
        self.assertTrue(any(not self._inside_polygon(home, moema) for home in data["home_coordinates"]))

    def test_real_catalog_is_the_cleaned_raw_export(self):
        real = pd.read_csv(REAL_CATALOG, sep=";")
        cleaned = clean_real_catalog(RAW_REAL_CATALOG)

        pd.testing.assert_frame_equal(real, cleaned, check_dtype=False)
        self.assertFalse(real[["city", "district", "lat", "lon"]].isna().any().any())
        self.assertFalse(real["district"].str.strip().str.lower().eq("normal").any())
        self.assertLessEqual(_km_from_city_median(real).max(), MAX_KM_FROM_CITY)
        self.assertGreater(real["city"].nunique(), 1)

    def test_listings_of_one_building_stay_separate(self):
        raw = pd.read_csv(RAW_REAL_CATALOG, sep=";", low_memory=False)
        real = pd.read_csv(REAL_CATALOG, sep=";")

        self.assertTrue(real["id"].is_unique)
        self.assertLessEqual(len(real), raw["listing.id"].nunique())
        same_point = real.groupby(["address", "district", "lat", "lon"])["id"].nunique()
        self.assertGreater(same_point.max(), 1)

    def test_synthetic_instance_has_no_listings(self):
        data = load_instance("synthetic", "m7", num_properties=5, random_seed=42)
        self.assertNotIn("listings", data)
        self.assertEqual(data["num_nodes"], 6)
        self.assertEqual(data["num_brokers"], 3)
        self.assertAlmostEqual(data["home_coordinates"][0][0], 74.81469997204559)
        self.assertAlmostEqual(data["home_coordinates"][0][1], 26.19289236408897)

    @staticmethod
    def _inside_polygon(point, polygon, tolerance=0.02):
        """Half-plane test for a counter-clockwise convex polygon."""
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            edge_x = end[0] - start[0]
            edge_y = end[1] - start[1]
            length = math.hypot(edge_x, edge_y)
            if length == 0:
                continue
            signed_distance = (edge_x * (point[1] - start[1]) - edge_y * (point[0] - start[0])) / length
            if signed_distance < -tolerance:
                return False
        return True


if __name__ == "__main__":
    unittest.main()
