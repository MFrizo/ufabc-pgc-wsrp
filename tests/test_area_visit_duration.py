"""
Checks that the visits of a real instance last longer the larger the property.
"""

import unittest

from src.core.data_generator import AREA_REFERENCE, AUTO_BROKERS, _area_service_times, generate_wsrp_instance
from src.core.listings import load_instance
from src.models import INSTANCE_SETTINGS
from src.models.model_7 import build_model_m7
from src.solvers.engine import solve_model


class AreaVisitDurationTest(unittest.TestCase):
    def test_duration_grows_with_the_area_within_the_range(self):
        durations = _area_service_times([0, 10, 60, 120, 240, 500, AREA_REFERENCE, 5000], 60, 30)

        self.assertEqual(durations, [0, 30, 31, 34, 37, 44, 60, 90, 90])
        self.assertEqual(durations, [0] + sorted(durations[1:]))

    def test_without_variation_every_visit_lasts_s(self):
        self.assertEqual(_area_service_times([12, 80, 700], 60, 0), [0, 60, 60, 60])

    def test_real_visits_follow_the_listing_areas(self):
        data = load_instance("real", "m7", num_properties=8, random_seed=17, city="São Paulo", neighborhood="Moema")
        settings = INSTANCE_SETTINGS["m7"]
        expected = _area_service_times([listing["area"] for listing in data["listings"]], 60,
                                       settings["service_time_variation"])

        self.assertEqual(data["service_times"], expected)
        by_area = sorted(data["listings"], key=lambda listing: listing["area"])
        self.assertEqual([data["service_times"][listing["node"]] for listing in by_area],
                         sorted(data["service_times"][1:]))

    def test_real_visits_follow_the_areas_with_an_auto_fleet(self):
        data = load_instance("real", "m7", num_properties=8, random_seed=17, num_brokers=AUTO_BROKERS,
                             city="São Paulo", neighborhood="Moema")
        expected = _area_service_times([listing["area"] for listing in data["listings"]], 60, 30)

        self.assertEqual(data["service_times"], expected)

    def test_m7_solves_a_real_neighborhood_with_area_durations(self):
        data = load_instance("real", "m7", num_properties=8, random_seed=17, city="São Paulo", neighborhood="Moema")

        _, metrics = solve_model(build_model_m7(data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
        self.assertEqual(metrics["termination_condition"], "optimal")

    def test_synthetic_durations_are_still_drawn(self):
        data = generate_wsrp_instance(num_properties=6, random_seed=3, service_time_variation=30)
        self.assertEqual(len(data["service_times"]), 7)
        with self.assertRaises(ValueError):
            generate_wsrp_instance(num_properties=6, random_seed=3, areas=[50.0, 60.0])


if __name__ == "__main__":
    unittest.main()
