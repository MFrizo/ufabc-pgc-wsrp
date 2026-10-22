"""
Unit tests for Gurobi native multi-objective optimization (hierarchical, blended, lexicographic)
in M1.b and objective formulation benchmarking against default scalarized objectives.
"""

import unittest
import pyomo.environ as pyo

from src.models.model_1 import build_model_m1
from src.models.model_1_a import build_model_m1_a
from src.models.model_1_b import build_model_m1_b
from src.solvers.engine import get_objective_breakdown, solve_model
from src.solvers.multiobj_benchmark import compare_objectives


def _toy_m1_instance():
    """Small 2-property, 2-broker instance with fast deterministic solve."""
    return {
        'num_nodes': 3,
        'num_brokers': 2,
        'distance_matrix': [
            [0, 10, 20],
            [10, 0, 15],
            [20, 15, 0],
        ],
        'travel_times': [[
            [0, 10, 20],
            [10, 0, 15],
            [20, 15, 0],
        ]],
        'home_distances': [
            [0, 5, 12],
            [0, 14, 6],
        ],
        'home_travel_times': [[
            [0, 5, 12],
            [0, 14, 6],
        ]],
        'service_times': [0, 30, 30],
        'fixed_visits': [1, 2],
        'earliest_start': [0, 60, 120],
        'assigned_broker': [0, 0, 0],
        'shift_start': [0, 0],
        'shift_end': [540, 540],
        'max_day_length': 600,
    }


class TestGurobiMultiObjective(unittest.TestCase):
    def test_m1_b_builder_and_auto_solve(self):
        data = _toy_m1_instance()
        model = build_model_m1_b(data)
        self.assertTrue(getattr(model, 'is_multiobj', False))
        self.assertEqual(model.multiobj_mode, 'hierarchical')
        self.assertTrue(hasattr(model, 'multiobj_specs'))
        self.assertEqual(len(model.multiobj_specs), 5)

        # solve_model automatically detects is_multiobj without extra flags
        solved_model, metrics = solve_model(
            model, solver_name='gurobi_direct', mip_gap=0.0, tee=False
        )
        self.assertEqual(metrics['solver_status'], 'ok')
        self.assertEqual(metrics['termination_condition'], 'optimal')
        self.assertTrue(metrics['multiobj'])
        self.assertEqual(metrics['multiobj_mode'], 'hierarchical')
        self.assertEqual(len(metrics['multiobj_results']), 5)

        # Check breakdown
        breakdown = get_objective_breakdown(solved_model)
        self.assertEqual(len(breakdown), 5)
        fleet_item = next(b for b in breakdown if b['name'] == 'fleet')
        self.assertGreaterEqual(fleet_item['value'], 1.0)

    def test_m1_b_hierarchical_multiobj(self):
        data = _toy_m1_instance()
        model = build_model_m1_b(data, multiobj_mode='hierarchical')

        _, metrics = solve_model(
            model, solver_name='gurobi_direct', mip_gap=0.0, tee=False
        )
        self.assertEqual(metrics['solver_status'], 'ok')
        self.assertEqual(metrics['termination_condition'], 'optimal')
        self.assertEqual(metrics['multiobj_mode'], 'hierarchical')
        self.assertEqual(len(metrics['multiobj_results']), 5)

    def test_m1_b_blended_matches_scalar_objective(self):
        data = _toy_m1_instance()

        # Scalar solve on m1.b with multiobj=False
        m_scalar = build_model_m1_b(data)
        _, metrics_scalar = solve_model(m_scalar, solver_name='gurobi_direct', mip_gap=0.0, multiobj=False, tee=False)
        self.assertEqual(metrics_scalar['termination_condition'], 'optimal')
        scalar_val = pyo.value(m_scalar.obj)

        # Multi-objective blended solve
        m_blended = build_model_m1_b(data, multiobj_mode='blended')
        _, metrics_blended = solve_model(
            m_blended, solver_name='gurobi_direct', mip_gap=0.0, tee=False
        )
        self.assertEqual(metrics_blended['termination_condition'], 'optimal')
        blended_eval = pyo.value(m_blended.obj)

        self.assertAlmostEqual(scalar_val, blended_eval, places=4)

    def test_m1_b_lexicographic_multiobj(self):
        data = _toy_m1_instance()
        model = build_model_m1_b(data, multiobj_mode='lexicographic')
        _, metrics = solve_model(
            model, solver_name='gurobi_direct', mip_gap=0.0, tee=False
        )
        self.assertEqual(metrics['termination_condition'], 'optimal')
        priorities = [r['priority'] for r in metrics['multiobj_results']]
        # Priorities should be strictly descending
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_compare_objectives_benchmark(self):
        data = _toy_m1_instance()
        results = compare_objectives(data, model_version='m1.b', modes=('hierarchical', 'blended'), print_table=False)
        self.assertIn('default', results['runs'])
        self.assertIn('gurobi_hierarchical', results['runs'])
        self.assertIn('gurobi_blended', results['runs'])

        # Both multi-objective runs should be optimal
        for mode in ('gurobi_hierarchical', 'gurobi_blended'):
            run = results['runs'][mode]
            self.assertEqual(run['metrics']['termination_condition'], 'optimal')
            self.assertIsNotNone(run['scalar_objective'])

    def test_unsupported_solver_raises_error(self):
        data = _toy_m1_instance()
        model = build_model_m1_b(data)
        with self.assertRaises(ValueError):
            solve_model(model, solver_name='cbc', multiobj=True, tee=False)

    def test_models_without_specs_raise_error_when_multiobj_requested(self):
        data = _toy_m1_instance()
        # M1 and M1.a do not have multiobj_specs defined
        m1 = build_model_m1(data)
        self.assertFalse(hasattr(m1, 'multiobj_specs'))
        with self.assertRaises(ValueError):
            solve_model(m1, solver_name='gurobi_direct', multiobj=True, tee=False)

        m1_a = build_model_m1_a(data)
        self.assertFalse(hasattr(m1_a, 'multiobj_specs'))
        with self.assertRaises(ValueError):
            solve_model(m1_a, solver_name='gurobi_direct', multiobj=True, tee=False)

    def test_get_objective_breakdown_fallback_for_standard_models(self):
        data = _toy_m1_instance()
        m1_a = build_model_m1_a(data)
        solved_m1_a, _ = solve_model(m1_a, solver_name='gurobi_direct', mip_gap=0.0, tee=False)
        breakdown = get_objective_breakdown(solved_m1_a)
        self.assertEqual(len(breakdown), 5)
        names = {item['name'] for item in breakdown}
        self.assertEqual(names, {'fleet', 'travel_time', 'distance', 'delay', 'overtime'})


if __name__ == '__main__':
    unittest.main()
