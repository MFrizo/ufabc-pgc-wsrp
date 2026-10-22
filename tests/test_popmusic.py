"""
Unit tests for the POPMUSIC matheuristic decomposition solver (src.solvers.popmusic)
across M0, M1.a, M1.b, M2.a, and M3.a models.
"""

import unittest
import pyomo.environ as pyo

from src.models.model_0_0 import build_model_m0_0
from src.models.model_0_2 import build_model_m0_2
from src.models.model_1_a import build_model_m1_a
from src.models.model_1_b import build_model_m1_b
from src.models.model_2_a import build_model_m2_a
from src.models.model_3_a import pareto_front as pareto_front_m3_a
from src.solvers.engine import solve_model
from src.solvers.popmusic import compare_popmusic, solve_popmusic
from src.utils.parsers import extract_open_routes


def _three_broker_m1_instance() -> dict:
    """4-property, 3-broker instance for testing POPMUSIC sub-problems with r=2 < |K|=3."""
    return {
        'num_nodes': 5,
        'num_brokers': 3,
        'distance_matrix': [
            [0, 10, 12, 25, 28],
            [10, 0, 8, 22, 24],
            [12, 8, 0, 20, 22],
            [25, 22, 20, 0, 9],
            [28, 24, 22, 9, 0],
        ],
        'travel_times': [[
            [0, 10, 12, 25, 28],
            [10, 0, 8, 22, 24],
            [12, 8, 0, 20, 22],
            [25, 22, 20, 0, 9],
            [28, 24, 22, 9, 0],
        ]],
        'home_distances': [
            [0, 5, 7, 25, 27],
            [0, 24, 22, 6, 8],
            [0, 15, 15, 15, 15],
        ],
        'home_travel_times': [[
            [0, 5, 7, 25, 27],
            [0, 24, 22, 6, 8],
            [0, 15, 15, 15, 15],
        ]],
        'lunch_spot_distances': [
            [0, 6, 8, 20, 22],
            [0, 20, 18, 7, 9],
            [0, 12, 12, 12, 12],
        ],
        'lunch_spot_travel_times': [[
            [0, 6, 8, 20, 22],
            [0, 20, 18, 7, 9],
            [0, 12, 12, 12, 12],
        ]],
        'service_times': [0, 30, 30, 30, 30],
        'fixed_visits': [1, 2, 3, 4],
        'earliest_start': [0, 60, 110, 70, 120],
        'latest_start': [540, 60, 110, 70, 120],
        'assigned_broker': [0, 0, 0, 0, 0],
        'shift_start': [0, 0, 0],
        'shift_end': [540, 540, 540],
        'shifts': [
            [(0, 210), (270, 540)],
            [(0, 210), (270, 540)],
            [(0, 210), (270, 540)],
        ],
        'max_day_length': 600,
    }


class TestPopmusicMatheuristic(unittest.TestCase):
    def test_m1_a_popmusic_r2_on_3_brokers(self):
        data = _three_broker_m1_instance()

        # Solve without POPMUSIC (exact baseline)
        m_exact = build_model_m1_a(data)
        _, metrics_exact = solve_model(m_exact, mip_gap=0.0, tee=False, popmusic=False)
        self.assertEqual(metrics_exact['solver_status'], 'ok')
        exact_obj = pyo.value(m_exact.obj)

        # Solve with POPMUSIC (r=2 brokers per subproblem)
        m_pop = build_model_m1_a(data)
        _, metrics_pop = solve_model(
            m_pop, mip_gap=0.0, tee=False, popmusic=True, popmusic_r=2
        )
        self.assertEqual(metrics_pop['solver_status'], 'ok')
        self.assertTrue(metrics_pop['popmusic'])
        self.assertEqual(metrics_pop['popmusic_r'], 2)
        self.assertGreaterEqual(metrics_pop['popmusic_subproblems'], 1)
        self.assertLessEqual(
            metrics_pop['final_objective'], metrics_pop['initial_objective'] + 1e-5
        )

        # Verify valid routes and optimal objective reached on this 4-property instance
        routes = extract_open_routes(m_pop)
        self.assertIsNotNone(routes)
        self.assertAlmostEqual(pyo.value(m_pop.obj), exact_obj, places=3)

    def test_m1_b_popmusic_with_native_multiobj(self):
        data = _three_broker_m1_instance()
        m_pop = build_model_m1_b(data, multiobj_mode='hierarchical')
        _, metrics = solve_popmusic(m_pop, sub_size=2, mip_gap=0.0, tee=False)

        self.assertEqual(metrics['solver_status'], 'ok')
        self.assertTrue(metrics['popmusic'])
        self.assertTrue(metrics['multiobj'])
        self.assertEqual(metrics['multiobj_mode'], 'hierarchical')
        self.assertIn('multiobj_results', metrics)
        self.assertEqual(len(metrics['multiobj_results']), 5)

    def test_m2_a_popmusic_shift_routes_and_fairness(self):
        data = _three_broker_m1_instance()
        m_pop = build_model_m2_a(data)
        _, metrics = solve_popmusic(m_pop, sub_size=2, mip_gap=0.0, tee=False)

        self.assertEqual(metrics['solver_status'], 'ok')
        self.assertTrue(metrics['popmusic'])
        routes = extract_open_routes(m_pop)
        self.assertIsNotNone(routes)
        # All 4 properties must be covered across shifts
        visited = {node for seq in routes.values() for node in seq if node in m_pop.C}
        self.assertEqual(visited, {1, 2, 3, 4})

    def test_m3_a_pareto_front_with_popmusic(self):
        data = _three_broker_m1_instance()
        front_exact = pareto_front_m3_a(data, popmusic=False)
        front_pop = pareto_front_m3_a(data, popmusic=True, popmusic_r=2)

        self.assertGreaterEqual(len(front_pop), 1)
        self.assertEqual(
            [pt['brokers'] for pt in front_pop],
            [pt['brokers'] for pt in front_exact],
        )

    def test_closed_route_m0_2_and_single_broker_m0_0(self):
        # Single-broker M0.0 fallback
        tsp_data = {
            'num_nodes': 4,
            'distance_matrix': [
                [0, 5, 9, 8],
                [5, 0, 4, 7],
                [9, 4, 0, 3],
                [8, 7, 3, 0],
            ],
        }
        m0 = build_model_m0_0(tsp_data)
        _, metrics_m0 = solve_popmusic(m0, sub_size=2, tee=False)
        self.assertEqual(metrics_m0['solver_status'], 'ok')
        self.assertTrue(metrics_m0['popmusic'])

        # Multi-broker closed-route M0.2
        vrptw_data = {
            'num_nodes': 4,
            'num_brokers': 2,
            'distance_matrix': tsp_data['distance_matrix'],
            'travel_time': 10.0,
            'service_time': 20.0,
            'earliest_start': [0, 20, 60, 100],
            'latest_start': [300, 120, 160, 200],
        }
        m02 = build_model_m0_2(vrptw_data)
        _, metrics_m02 = solve_popmusic(m02, sub_size=1, tee=False)
        self.assertEqual(metrics_m02['solver_status'], 'ok')
        self.assertTrue(metrics_m02['popmusic'])

    def test_compare_popmusic_benchmark(self):
        data = _three_broker_m1_instance()
        res = compare_popmusic(data, model_version='m1.a', sub_size=2, print_table=False)
        self.assertIn('exact', res['runs'])
        self.assertIn('popmusic', res['runs'])
        self.assertAlmostEqual(res['runs']['popmusic']['gap_pct'], 0.0, places=2)


if __name__ == '__main__':
    unittest.main()
