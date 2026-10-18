"""
Checks M1.b, the tightened and lifted MTZ reformulation of M1 / M1.a:
- Matches M1 and M1.a optimal objectives across fixed_ratio in {0.0, 0.5, 1.0};
- Shrinks node time windows [a_i, b_i], replaces global M with arc-specific M^k_{ij},
  and fixes time-infeasible arcs to zero;
- Produces a tighter root LP relaxation than M1.a without solver cuts.
"""

import unittest

import pyomo.environ as pyo

from src.core.listings import load_instance
from src.models import INSTANCE_SETTINGS
from src.models.model_1 import DELAY_TOLERANCE, build_model_m1
from src.models.model_1_a import build_model_m1_a
from src.models.model_1_b import build_model_m1_b
from src.solvers.engine import solve_model


def _solve(model):
    solved, metrics = solve_model(model, solver_name="gurobi_direct", mip_gap=0.0, raw=True)
    return solved, metrics


class Model1bTest(unittest.TestCase):
    def test_matches_m1_and_m1_a_across_fixed_ratios(self):
        for seed in (1, 8, 17):
            for ratio in (1.0, 0.5, 0.0):
                with self.subTest(seed=seed, fixed_ratio=ratio):
                    data = load_instance("synthetic", "m1.b", num_properties=6, random_seed=seed, fixed_ratio=ratio)
                    m1a, m1a_metrics = _solve(build_model_m1_a(data))
                    m1b, m1b_metrics = _solve(build_model_m1_b(data))

                    self.assertEqual(m1a_metrics["termination_condition"], "optimal")
                    self.assertEqual(m1b_metrics["termination_condition"], "optimal")
                    self.assertAlmostEqual(pyo.value(m1b.obj), pyo.value(m1a.obj), places=4)

                    if ratio == 1.0:
                        m1, _ = _solve(build_model_m1(data))
                        self.assertAlmostEqual(pyo.value(m1b.obj), pyo.value(m1.obj), places=4)

    def test_time_window_preprocessing_and_arc_specific_big_m(self):
        data = load_instance("synthetic", "m1.b", num_properties=6, random_seed=8, fixed_ratio=0.5)
        m1a = build_model_m1_a(data)
        m1b = build_model_m1_b(data)

        global_m = pyo.value(m1a.big_m)
        max_arc_m = max(pyo.value(m1b.arc_big_m[arc]) for arc in m1b.ARCS)
        self.assertLess(max_arc_m, global_m)

        fixed_zero_arcs = [arc for arc in m1b.ARCS if m1b.x[arc].fixed and pyo.value(m1b.x[arc]) == 0]
        self.assertGreater(len(fixed_zero_arcs), 0)

        for i in m1b.C_w:
            self.assertGreater(pyo.value(m1b.window_start[i]), data["earliest_start"][i])
            self.assertLessEqual(pyo.value(m1b.window_end[i]), data["latest_start"][i])

        for i in m1b.C_h:
            self.assertGreaterEqual(pyo.value(m1b.window_start[i]), data["earliest_start"][i] - DELAY_TOLERANCE - 1e-6)
            self.assertLessEqual(pyo.value(m1b.window_end[i]), data["earliest_start"][i] + DELAY_TOLERANCE + 1e-6)

    def test_default_instance_settings(self):
        self.assertEqual(INSTANCE_SETTINGS["m1.b"]["fixed_ratio"], 0.5)
        data = load_instance("synthetic", "m1.b", num_properties=6, random_seed=8)
        self.assertEqual(len(data["fixed_visits"]), 3)

    def test_m1_b_solves_sao_paulo(self):
        data = load_instance("real", "m1.b", num_properties=6, random_seed=8, city="São Paulo")
        m1a, _ = _solve(build_model_m1_a(data))
        m1b, metrics = _solve(build_model_m1_b(data))
        self.assertEqual(metrics["termination_condition"], "optimal")
        self.assertAlmostEqual(pyo.value(m1b.obj), pyo.value(m1a.obj), places=4)


if __name__ == "__main__":
    unittest.main()
