"""
Builds instances from one city, or one neighborhood of it, of the real catalog, and checks the synthetic
ones are unchanged.
"""

import math
import unittest

from src.core.data_generator import AUTO_BROKERS, generate_wsrp_instance
from src.core.listings import MAP_CENTER, MAP_UNITS_PER_KM, load_instance, select_listings
from src.models import INSTANCE_SETTINGS, SINGLE_BROKER_MODELS
from src.models.model_7 import build_model_m7
from src.solvers.engine import solve_model
from src.utils.logger import project_logger
from src.utils.real_catalog import KM_PER_DEGREE_LAT, KM_PER_DEGREE_LON, REAL_CATALOG, clean_real_catalog


class RealInstancesTest(unittest.TestCase):
    def test_sample_comes_from_one_neighborhood(self):
        data = load_instance("real", "m7", num_properties=5, random_seed=17, city="São Paulo", neighborhood="Moema")
        moema = select_listings(clean_real_catalog(REAL_CATALOG), "São Paulo", "Moema")

        self.assertEqual(data["num_nodes"], 6)
        self.assertEqual([listing["node"] for listing in data["listings"]], [1, 2, 3, 4, 5])
        self.assertEqual(len({listing["id"] for listing in data["listings"]}), 5)
        self.assertTrue({listing["id"] for listing in data["listings"]} <= set(moema["id"].astype(str)))
        for listing in data["listings"]:
            self.assertEqual(listing["city"], "São Paulo")
            self.assertEqual(listing["district"], "Moema")

    def test_house_graph_follows_listing_coordinates(self):
        data = load_instance("real", "m7", num_properties=5, random_seed=17, city="São Paulo", neighborhood="Moema")
        listings = data["listings"]
        origin_lat = sum(listing["lat"] for listing in listings) / len(listings)
        origin_lon = sum(listing["lon"] for listing in listings) / len(listings)
        km_per_degree_lon = KM_PER_DEGREE_LON * math.cos(math.radians(origin_lat))

        self.assertEqual(data["coordinates"][0], list(MAP_CENTER))
        for a in listings:
            for b in listings:
                km = math.hypot((a["lat"] - b["lat"]) * KM_PER_DEGREE_LAT,
                                (a["lon"] - b["lon"]) * km_per_degree_lon)
                self.assertAlmostEqual(data["distance_matrix"][a["node"]][b["node"]], km * MAP_UNITS_PER_KM, places=1)

    def test_m7_solves_a_real_neighborhood(self):
        data = load_instance("real", "m7", num_properties=5, random_seed=17, city="São Paulo", neighborhood="Moema")

        solved_model, metrics = solve_model(build_model_m7(data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
        self.assertEqual(metrics["termination_condition"], "optimal")
        self.assertIsNotNone(solved_model)

    def test_real_instance_needs_a_city(self):
        for city in (None, "", " "):
            with self.assertRaises(ValueError):
                load_instance("real", "m7", city=city, neighborhood="Moema")

    def test_without_a_neighborhood_the_sample_comes_from_the_whole_city(self):
        city = select_listings(clean_real_catalog(REAL_CATALOG), "São Paulo")
        for neighborhood in (None, "", " "):
            data = load_instance("real", "m7", num_properties=20, random_seed=17, city="São Paulo",
                                 neighborhood=neighborhood)

            self.assertEqual(data["num_nodes"], 21)
            self.assertTrue({listing["id"] for listing in data["listings"]} <= set(city["id"].astype(str)))
            self.assertTrue(all(listing["city"] == "São Paulo" for listing in data["listings"]))
            self.assertGreater(len({listing["district"] for listing in data["listings"]}), 1)

    def test_m7_solves_a_whole_city(self):
        data = load_instance("real", "m7", num_properties=8, random_seed=17, city="São Paulo")

        _, metrics = solve_model(build_model_m7(data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
        self.assertEqual(metrics["termination_condition"], "optimal")

    def test_neighborhood_must_exist_and_hold_the_sample(self):
        with self.assertRaises(ValueError):
            load_instance("real", "m7", city="São Paulo", neighborhood="Copacabana")
        with self.assertRaises(ValueError):
            load_instance("real", "m7", city="Atlantis", neighborhood="Moema")
        with self.assertRaises(ValueError):
            load_instance("real", "m7", num_properties=100_000, city="São Paulo", neighborhood="Moema")

    def test_synthetic_instance_is_the_generator(self):
        for model, settings in INSTANCE_SETTINGS.items():
            self.assertEqual(load_instance("synthetic", model, num_properties=6, random_seed=3),
                             generate_wsrp_instance(num_properties=6, random_seed=3, **settings))

    def test_num_brokers_overrides_the_model_setting(self):
        self.assertEqual(load_instance("synthetic", "m2", num_brokers=4)["num_brokers"], 4)
        data = load_instance("real", "m7", num_properties=5, random_seed=17, num_brokers=2,
                             city="São Paulo", neighborhood="Moema")
        self.assertEqual(data["num_brokers"], 2)
        self.assertEqual(len(data["home_coordinates"]), 2)

    def test_single_broker_models_warn_and_ignore_num_brokers(self):
        for model in SINGLE_BROKER_MODELS:
            for num_brokers in (4, AUTO_BROKERS):
                with self.assertLogs(project_logger, level="WARNING") as logs:
                    data = load_instance("synthetic", model, num_properties=6, random_seed=3, num_brokers=num_brokers)

                self.assertIn("single broker", logs.output[0])
                self.assertEqual(data, load_instance("synthetic", model, num_properties=6, random_seed=3))

    def test_unknown_dataset_is_rejected(self):
        with self.assertRaises(ValueError):
            load_instance("zap", "m7")


if __name__ == "__main__":
    unittest.main()
