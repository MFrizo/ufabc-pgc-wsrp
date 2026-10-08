"""
Checks the fleet sized from the visits (num_brokers="auto") and the explicit broker override.
"""

import unittest

import pyomo.environ as pyo

from src.core.data_generator import AUTO_BROKERS, SPARE_BROKERS, generate_wsrp_instance
from src.core.listings import load_instance
from src.models.model_7 import build_model_m7
from src.solvers.engine import solve_model


class BrokerFleetTest(unittest.TestCase):
    def test_auto_fleet_adds_spares_to_the_hidden_schedule(self):
        data = load_instance("synthetic", "m7", num_properties=12, random_seed=42, num_brokers=AUTO_BROKERS)
        schedule, fleet = data["schedule_brokers"], data["num_brokers"]

        self.assertGreaterEqual(schedule, 1)
        self.assertEqual(fleet, min(12, schedule + SPARE_BROKERS))
        self.assertGreater(fleet, schedule)
        self.assertEqual(len(data["home_coordinates"]), fleet)
        self.assertEqual(len(data["home_distances"]), fleet)
        self.assertTrue(all(len(period) == fleet for period in data["home_travel_times"]))
        self.assertEqual(len(data["shift_start"]), fleet)
        self.assertEqual(len(data["shift_end"]), fleet)
        self.assertTrue(all(broker in range(fleet + 1) for broker in data["assigned_broker"]))

    def test_auto_fleet_keeps_the_first_homes(self):
        auto = generate_wsrp_instance(num_properties=12, random_seed=42, num_brokers=AUTO_BROKERS)
        pool = generate_wsrp_instance(num_properties=12, random_seed=42, num_brokers=12)

        self.assertEqual(auto["home_coordinates"], pool["home_coordinates"][:auto["num_brokers"]])

    def test_auto_fleet_grows_with_the_visits(self):
        fleets = [load_instance("synthetic", "m7", num_properties=n, random_seed=1,
                                num_brokers=AUTO_BROKERS)["schedule_brokers"] for n in (5, 10, 20)]

        self.assertEqual(fleets, sorted(fleets))
        self.assertLess(fleets[0], fleets[-1])

    def test_m7_solves_with_an_auto_fleet_in_one_neighborhood(self):
        data = load_instance("real", "m7", num_properties=10, random_seed=42, city="São Paulo",
                             neighborhood="Moema", num_brokers=AUTO_BROKERS)

        solved_model, metrics = solve_model(build_model_m7(data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
        self.assertEqual(metrics["termination_condition"], "optimal")
        used = round(sum(pyo.value(solved_model.y[k]) for k in solved_model.K))
        self.assertGreaterEqual(used, 1)
        self.assertLessEqual(used, data["num_brokers"])

    def test_fixed_fleet_is_the_hidden_schedule(self):
        data = load_instance("synthetic", "m7", num_properties=12, random_seed=42)

        self.assertEqual(data["num_brokers"], 3)
        self.assertEqual(data["schedule_brokers"], 3)

    def test_explicit_fleet_overrides_the_model_setting(self):
        data = load_instance("synthetic", "m2", num_properties=8, random_seed=42, num_brokers=4)

        self.assertEqual(data["num_brokers"], 4)
        self.assertEqual(data["schedule_brokers"], 4)

    def test_single_broker_models_reject_a_fleet(self):
        with self.assertRaises(ValueError):
            load_instance("synthetic", "m1", num_brokers=AUTO_BROKERS)
        for invalid in (0, -1, "many", 2.5, True):
            with self.assertRaises(ValueError):
                load_instance("synthetic", "m7", num_brokers=invalid)


if __name__ == "__main__":
    unittest.main()
