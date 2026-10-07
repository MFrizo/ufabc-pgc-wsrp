"""
Runs a model on a sample of the real São Paulo rental catalog.
"""

import unittest

from src.core.listings import REAL_CATALOG, load_instance, load_real_catalog
from src.models.model_7 import build_model_m7
from src.solvers.engine import solve_model


class RealDatasetTest(unittest.TestCase):
    def test_m7_solves_a_real_sample(self):
        data = load_instance("real", "m7", num_properties=5, random_seed=42)
        catalog = load_real_catalog(REAL_CATALOG)
        catalog_keys = set(zip(catalog["address"], catalog["district"]))

        self.assertEqual(data["num_nodes"], 6)
        self.assertEqual(len(data["listings"]), 5)
        self.assertGreater(len(catalog), 1000)
        for listing in data["listings"]:
            self.assertIn((listing["address"], listing["district"]), catalog_keys)
            self.assertEqual(listing["city"], "São Paulo")
            self.assertGreaterEqual(data["service_times"][listing["node"]], 30)
            self.assertLessEqual(data["service_times"][listing["node"]], 90)

        solved_model, metrics = solve_model(build_model_m7(data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
        self.assertEqual(metrics["solver_status"], "ok")
        self.assertEqual(metrics["termination_condition"], "optimal")
        self.assertIsNotNone(solved_model)

    def test_synthetic_instance_has_no_listings(self):
        data = load_instance("synthetic", "m7", num_properties=5, random_seed=42)
        self.assertNotIn("listings", data)
        self.assertEqual(data["num_nodes"], 6)
        self.assertEqual(data["num_brokers"], 3)


if __name__ == "__main__":
    unittest.main()
