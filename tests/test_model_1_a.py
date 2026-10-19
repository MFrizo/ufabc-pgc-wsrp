"""
Checks M1 (with booked and flexible visits across fixed_ratio in [0, 1]) and M1.a,
the tightened and lifted MTZ reformulation of M1:
- M1 respects booked visits' soft windows and flexible visits' day windows for any fixed_ratio;
- M1.a matches M1 optimal objectives across fixed_ratio in {0.0, 0.5, 1.0};
- M1.a shrinks node time windows [a_i, b_i], replaces global M with arc-specific M^k_{ij},
  and fixes time-infeasible arcs to zero.
"""

import unittest

import pyomo.environ as pyo

from src.core.listings import load_instance
from src.models import INSTANCE_SETTINGS
from src.models.model_1 import DELAY_TOLERANCE, build_model_m1
from src.models.model_1_a import build_model_m1_a
from src.solvers.engine import solve_model


def _solve(model):
    solved, metrics = solve_model(model, solver_name="gurobi_direct", mip_gap=0.0, raw=True)
    return solved, metrics


class Model1aTest(unittest.TestCase):
    def test_m1_booked_and_flexible_visits_across_ratios(self):
        for ratio in (0.0, 0.5, 1.0):
            data = load_instance("synthetic", "m1", num_properties=6, random_seed=8, fixed_ratio=ratio)
            model, metrics = _solve(build_model_m1(data))
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

    def test_m1_a_matches_m1_across_fixed_ratios(self):
        for seed in (1, 8, 17):
            for ratio in (1.0, 0.5, 0.0):
                with self.subTest(seed=seed, fixed_ratio=ratio):
                    data = load_instance("synthetic", "m1", num_properties=6, random_seed=seed, fixed_ratio=ratio)
                    m1, m1_metrics = _solve(build_model_m1(data))
                    m1a, m1a_metrics = _solve(build_model_m1_a(data))

                    self.assertEqual(m1_metrics["termination_condition"], "optimal")
                    self.assertEqual(m1a_metrics["termination_condition"], "optimal")
                    self.assertAlmostEqual(pyo.value(m1a.obj), pyo.value(m1.obj), places=4)

    def test_time_window_preprocessing_and_arc_specific_big_m(self):
        data = load_instance("synthetic", "m1.a", num_properties=6, random_seed=8, fixed_ratio=0.5)
        m1 = build_model_m1(data)
        m1a = build_model_m1_a(data)

        global_m = pyo.value(m1.big_m)
        max_arc_m = max(pyo.value(m1a.arc_big_m[arc]) for arc in m1a.ARCS)
        self.assertLess(max_arc_m, global_m)

        fixed_zero_arcs = [arc for arc in m1a.ARCS if m1a.x[arc].fixed and pyo.value(m1a.x[arc]) == 0]
        self.assertGreater(len(fixed_zero_arcs), 0)

        for i in m1a.C_w:
            self.assertGreater(pyo.value(m1a.window_start[i]), data["earliest_start"][i])
            self.assertLessEqual(pyo.value(m1a.window_end[i]), data["latest_start"][i])

        for i in m1a.C_h:
            self.assertGreaterEqual(pyo.value(m1a.window_start[i]), data["earliest_start"][i] - DELAY_TOLERANCE - 1e-6)
            self.assertLessEqual(pyo.value(m1a.window_end[i]), data["earliest_start"][i] + DELAY_TOLERANCE + 1e-6)

    def test_default_instance_settings(self):
        self.assertEqual(INSTANCE_SETTINGS["m1"]["fixed_ratio"], 1.0)
        self.assertEqual(INSTANCE_SETTINGS["m1.a"]["fixed_ratio"], 1.0)
        data = load_instance("synthetic", "m1.a", num_properties=6, random_seed=8)
        self.assertEqual(len(data["fixed_visits"]), 6)

    def test_m1_a_solves_sao_paulo(self):
        for ratio in (1.0, 0.5):
            data = load_instance("real", "m1.a", num_properties=6, random_seed=8, city="São Paulo", fixed_ratio=ratio)
            m1, _ = _solve(build_model_m1(data))
            m1a, metrics = _solve(build_model_m1_a(data))
            self.assertEqual(metrics["termination_condition"], "optimal")
            self.assertAlmostEqual(pyo.value(m1a.obj), pyo.value(m1.obj), places=4)


if __name__ == "__main__":
    unittest.main()
