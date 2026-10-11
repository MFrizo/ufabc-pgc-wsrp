"""
Checks the Pareto front of M3.

The feasible routes are M1's. The brokers' cost is the minutes of a route that fall
outside that broker's shifts, a day worked on a day off, and the detour to his lunch
spot. A larger fleet is kept only when it costs the brokers less.
"""

import unittest

import pyomo.environ as pyo

from src.models.model_3 import build_model_m3, pareto_front
from src.solvers.engine import solve_model


def _zeros(n):
    return [[0] * n for _ in range(n)]


def _instance():
    """
    Two visits a long way apart. Each broker's shift covers one of them and the lunch,
    and neither shift covers both, so one broker finishes outside his shift.
    """
    n = 3
    row = [0] * n
    return {
        'num_nodes': n,
        'num_brokers': 2,
        'distance_matrix': _zeros(n),
        'travel_times': [_zeros(n)],
        'home_distances': [row, row],
        'home_travel_times': [[row, row]],
        'lunch_spot_distances': [row, row],
        'lunch_spot_travel_times': [[row, row]],
        'service_times': [0, 20, 20],
        'earliest_start': [0, 60, 500],
        'assigned_broker': [0, 0, 0],
        'shift_start': [0, 0],
        'shift_end': [540, 540],
        'shifts': [[(0, 400)], [(180, 600)]],
    }


def _day_off_instance():
    """One visit, and a second broker whose day off would cost him the whole day."""
    n = 2
    row = [0] * n
    return {
        'num_nodes': n,
        'num_brokers': 2,
        'distance_matrix': _zeros(n),
        'travel_times': [_zeros(n)],
        'home_distances': [row, row],
        'home_travel_times': [[row, row]],
        'lunch_spot_distances': [row, row],
        'lunch_spot_travel_times': [[row, row]],
        'service_times': [0, 20],
        'earliest_start': [0, 60],
        'assigned_broker': [0, 0],
        'shift_start': [0, 0],
        'shift_end': [540, 540],
        'shifts': [[(0, 400)], []],
    }


class ParetoFrontTest(unittest.TestCase):
    def test_a_day_off_is_not_used_when_another_broker_can_work(self):
        front = pareto_front(_day_off_instance())

        self.assertEqual([point['brokers'] for point in front], [1])
        solved, metrics = solve_model(build_model_m3(_day_off_instance(), fleet_cap=2),
                                      solver_name='gurobi_direct', mip_gap=0.0, raw=True)
        self.assertEqual(metrics['termination_condition'], 'optimal')
        self.assertEqual(int(round(pyo.value(solved.y[2]))), 0)
        self.assertLess(pyo.value(solved.broker_cost), 720)

    def test_splitting_the_visits_lowers_the_broker_cost(self):
        front = pareto_front(_instance())

        self.assertEqual([point['brokers'] for point in front], [1, 2])
        self.assertGreater(front[0]['broker_cost'], front[1]['broker_cost'] + 1)

    def test_a_generated_instance_returns_a_nondominated_front(self):
        from src.core.listings import load_instance

        data = load_instance('synthetic', 'm3', num_properties=3, random_seed=8)
        front = pareto_front(data)

        self.assertGreaterEqual(len(front), 1)
        self.assertEqual([point['brokers'] for point in front], sorted(point['brokers'] for point in front))
        for earlier, later in zip(front, front[1:]):
            self.assertLess(earlier['brokers'], later['brokers'])
            self.assertLess(later['broker_cost'], earlier['broker_cost'] - 1e-4)

    def test_allowing_more_brokers_cannot_raise_the_broker_cost(self):
        data = _instance()
        costs = []
        for cap in (1, 2):
            solved, metrics = solve_model(build_model_m3(data, fleet_cap=cap),
                                          solver_name='gurobi_direct', mip_gap=0.0, raw=True)
            self.assertEqual(metrics['termination_condition'], 'optimal')
            costs.append(pyo.value(solved.broker_cost))
        self.assertLessEqual(costs[1], costs[0] + 1e-4)


if __name__ == '__main__':
    unittest.main()
