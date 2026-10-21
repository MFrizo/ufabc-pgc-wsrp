"""
Checks M2 (with booked and flexible visits across fixed_ratio in [0, 1]) and M2.a,
the tightened and lifted MTZ reformulation of M2:
- M2 respects booked visits' soft windows and flexible visits' day windows for any fixed_ratio;
- M2.a matches M2 optimal objectives across fixed_ratio in {0.0, 0.5, 1.0};
- M2.a shrinks node time windows [a_i, b_i], replaces global M with arc-specific M^r_{ij}
  and shift-specific M_r^span, and fixes time-infeasible arcs to zero.
"""

import unittest

import pyomo.environ as pyo

from src.core.listings import load_instance
from src.models import INSTANCE_SETTINGS
from src.models.model_2 import DELAY_TOLERANCE, build_model_m2
from src.models.model_2_a import build_model_m2_a
from src.solvers.engine import solve_model


def _solve(model):
    solved, metrics = solve_model(model, solver_name="gurobi_direct", mip_gap=0.0, raw=False)
    return solved, metrics


class Model2aTest(unittest.TestCase):
    def test_m2_booked_and_flexible_visits_across_ratios(self):
        for ratio in (0.0, 0.5, 1.0):
            data = load_instance("synthetic", "m2", num_properties=4, random_seed=8, fixed_ratio=ratio)
            model, metrics = _solve(build_model_m2(data))
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

    def test_m2_a_matches_m2_across_fixed_ratios(self):
        for seed in (1, 8, 17):
            for ratio in (1.0, 0.5, 0.0):
                with self.subTest(seed=seed, fixed_ratio=ratio):
                    data = load_instance("synthetic", "m2", num_properties=4, random_seed=seed, fixed_ratio=ratio)
                    m2, m2_metrics = _solve(build_model_m2(data))
                    m2a, m2a_metrics = _solve(build_model_m2_a(data))

                    self.assertEqual(m2_metrics["termination_condition"], "optimal")
                    self.assertEqual(m2a_metrics["termination_condition"], "optimal")
                    self.assertAlmostEqual(pyo.value(m2a.obj), pyo.value(m2.obj), places=4)

    def test_time_window_preprocessing_and_arc_specific_big_m(self):
        data = load_instance("synthetic", "m2.a", num_properties=4, random_seed=8, fixed_ratio=0.5)
        m2 = build_model_m2(data)
        m2a = build_model_m2_a(data)

        global_m = pyo.value(m2.big_m)
        max_arc_m = max(pyo.value(m2a.arc_big_m[arc]) for arc in m2a.ARCS)
        self.assertLess(max_arc_m, global_m)

        max_span_m = max(pyo.value(m2a.span_big_m[r]) for r in m2a.R)
        self.assertLess(max_span_m, global_m)

        fixed_zero_arcs = [arc for arc in m2a.ARCS if m2a.x[arc].fixed and pyo.value(m2a.x[arc]) == 0]
        self.assertGreater(len(fixed_zero_arcs), 0)

        for i in m2a.C_w:
            self.assertGreater(pyo.value(m2a.window_start[i]), data["earliest_start"][i])
            self.assertLessEqual(pyo.value(m2a.window_end[i]), data["latest_start"][i])

        for i in m2a.C_h:
            self.assertGreaterEqual(pyo.value(m2a.window_start[i]), data["earliest_start"][i] - DELAY_TOLERANCE - 1e-6)
            self.assertLessEqual(pyo.value(m2a.window_end[i]), data["earliest_start"][i] + DELAY_TOLERANCE + 1e-6)

    def test_default_instance_settings(self):
        self.assertEqual(INSTANCE_SETTINGS["m2"]["fixed_ratio"], 1.0)
        self.assertEqual(INSTANCE_SETTINGS["m2.a"]["fixed_ratio"], 1.0)
        data = load_instance("synthetic", "m2.a", num_properties=4, random_seed=8)
        self.assertEqual(len(data["fixed_visits"]), 4)

    def test_m2_a_solves_sao_paulo(self):
        for ratio in (1.0, 0.5):
            data = load_instance("real", "m2.a", num_properties=4, random_seed=8, city="São Paulo", fixed_ratio=ratio)
            m2, _ = _solve(build_model_m2(data))
            m2a, metrics = _solve(build_model_m2_a(data))
            self.assertEqual(metrics["termination_condition"], "optimal")
            self.assertAlmostEqual(pyo.value(m2a.obj), pyo.value(m2.obj), places=4)


if __name__ == "__main__":
    unittest.main()
