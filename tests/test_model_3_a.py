"""
Checks M3 (with booked and flexible visits across fixed_ratio in [0, 1]) and M3.a,
the tightened and lifted MTZ reformulation of M3:
- M3.a matches M3 optimal broker_cost and Pareto front across fixed_ratio in {0.0, 0.5, 1.0};
- M3.a replaces global M in shift-overlap constraints with tight shift/broker-specific bounds
  and builds on top of M1.a's tightened and lifted MTZ polyhedron.
"""

import unittest

import pyomo.environ as pyo

from src.core.listings import load_instance
from src.models import INSTANCE_SETTINGS
from src.models.model_3 import build_model_m3, pareto_front
from src.models.model_3_a import build_model_m3_a, pareto_front as pareto_front_m3_a
from src.solvers.engine import solve_model
from tests.test_model_3 import _day_off_instance, _instance


def _solve(model):
    solved, metrics = solve_model(model, solver_name="gurobi_direct", mip_gap=0.0, raw=True)
    return solved, metrics


class Model3aTest(unittest.TestCase):
    def test_m3_a_matches_m3_on_unit_instances(self):
        for data in (_instance(), _day_off_instance()):
            front_m3 = pareto_front(data)
            front_m3a = pareto_front_m3_a(data)
            self.assertEqual([p["brokers"] for p in front_m3a], [p["brokers"] for p in front_m3])
            for p3, p3a in zip(front_m3, front_m3a):
                self.assertAlmostEqual(p3a["broker_cost"], p3["broker_cost"], places=4)

    def test_m3_a_matches_m3_across_fixed_ratios(self):
        for seed in (1, 8):
            for ratio in (1.0, 0.5, 0.0):
                with self.subTest(seed=seed, fixed_ratio=ratio):
                    data = load_instance("synthetic", "m3", num_properties=3, random_seed=seed, fixed_ratio=ratio)
                    for cap in (1, 2, 3):
                        m3, m3_metrics = _solve(build_model_m3(data, fleet_cap=cap))
                        m3a, m3a_metrics = _solve(build_model_m3_a(data, fleet_cap=cap))

                        self.assertEqual(m3_metrics["termination_condition"], m3a_metrics["termination_condition"])
                        if m3_metrics["termination_condition"] == "optimal":
                            self.assertAlmostEqual(pyo.value(m3a.broker_cost), pyo.value(m3.broker_cost), places=4)

    def test_m3_a_pareto_front_matches_m3_across_ratios(self):
        for ratio in (1.0, 0.5):
            data = load_instance("synthetic", "m3.a", num_properties=3, random_seed=8, fixed_ratio=ratio)
            front_m3 = pareto_front(data)
            front_m3a = pareto_front_m3_a(data)
            self.assertEqual([p["brokers"] for p in front_m3a], [p["brokers"] for p in front_m3])
            for p3, p3a in zip(front_m3, front_m3a):
                self.assertAlmostEqual(p3a["broker_cost"], p3["broker_cost"], places=4)

    def test_tight_shift_overlap_bounds_have_no_global_big_m(self):
        data = load_instance("synthetic", "m3.a", num_properties=3, random_seed=8, fixed_ratio=0.5)
        m3 = build_model_m3(data)
        m3a = build_model_m3_a(data)

        self.assertFalse(hasattr(m3a, "big_m"))
        global_m = pyo.value(m3.big_m)
        max_arc_m = max(pyo.value(m3a.arc_big_m[arc]) for arc in m3a.ARCS)
        self.assertLess(max_arc_m, global_m)

    def test_default_instance_settings(self):
        self.assertEqual(INSTANCE_SETTINGS["m3"]["fixed_ratio"], 1.0)
        self.assertEqual(INSTANCE_SETTINGS["m3.a"]["fixed_ratio"], 1.0)
        data = load_instance("synthetic", "m3.a", num_properties=3, random_seed=8)
        self.assertEqual(len(data["fixed_visits"]), 3)


if __name__ == "__main__":
    unittest.main()
