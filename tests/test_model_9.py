"""
Checks M9, M7 with a share of flexible visits: booked visits keep their scheduled start,
flexible ones start anywhere in their window, and with every visit booked it is M7.
"""

import unittest

import pyomo.environ as pyo

from src.core.listings import load_instance
from src.models import INSTANCE_SETTINGS
from src.models.model_7 import DELAY_TOLERANCE, build_model_m7
from src.models.model_9 import build_model_m9
from src.solvers.engine import solve_model


def _solve(model):
    solved, metrics = solve_model(model, solver_name="gurobi_direct", mip_gap=0.0, raw=True)
    return solved, metrics


class Model9Test(unittest.TestCase):
    def test_with_every_visit_booked_it_is_m7(self):
        for seed in (1, 8, 17):
            data = load_instance("synthetic", "m9", num_properties=6, random_seed=seed, fixed_ratio=1.0)
            self.assertEqual(data, load_instance("synthetic", "m7", num_properties=6, random_seed=seed))

            m9, m9_metrics = _solve(build_model_m9(data))
            m7, m7_metrics = _solve(build_model_m7(data))
            self.assertEqual(m9_metrics["termination_condition"], "optimal")
            self.assertAlmostEqual(pyo.value(m9.obj), pyo.value(m7.obj), places=4)

    def test_booked_visits_keep_their_time_and_flexible_ones_their_window(self):
        for ratio in (0.0, 0.5):
            data = load_instance("synthetic", "m9", num_properties=6, random_seed=8, fixed_ratio=ratio)
            model, metrics = _solve(build_model_m9(data))
            self.assertEqual(metrics["termination_condition"], "optimal")

            self.assertEqual(sorted(model.C_h), data["fixed_visits"])
            for i in model.C_h:
                start = pyo.value(model.w[i])
                self.assertGreaterEqual(start, data["earliest_start"][i] - DELAY_TOLERANCE - 1e-6)
                self.assertLessEqual(start, data["earliest_start"][i] + DELAY_TOLERANCE + 1e-6)
            for i in model.C_w:
                start = pyo.value(model.w[i])
                self.assertGreaterEqual(start, data["earliest_start"][i] - 1e-6)
                self.assertLessEqual(start, data["latest_start"][i] + 1e-6)
                self.assertEqual(pyo.value(model.delay[i]), 0)

    def test_default_instance_books_half_the_visits(self):
        self.assertEqual(INSTANCE_SETTINGS["m9"]["fixed_ratio"], 0.5)
        data = load_instance("synthetic", "m9", num_properties=6, random_seed=8)
        self.assertEqual(len(data["fixed_visits"]), 3)

    def test_m9_solves_a_real_neighborhood(self):
        data = load_instance("real", "m9", num_properties=6, random_seed=8, city="São Paulo", neighborhood="Moema")
        _, metrics = _solve(build_model_m9(data))
        self.assertEqual(metrics["termination_condition"], "optimal")


if __name__ == "__main__":
    unittest.main()
