"""
Checks that M1 and M2 charge travel time, and use distance only to break a tie.

One visit can go to either of two brokers. Equal travel times go to the nearer
broker. A minute less driving beats any saving in distance.
"""

import unittest

import pyomo.environ as pyo

from src.models.model_1 import build_model_m1
from src.models.model_2 import build_model_m2
from src.solvers.engine import solve_model


def _m1(travel, distance):
    """One visit, two brokers, one period. travel and distance are 2 by 2 home matrices."""
    return {
        'num_nodes': 2,
        'num_brokers': 2,
        'distance_matrix': [[0, 0], [0, 0]],
        'travel_times': [[[0, 0], [0, 0]]],
        'home_distances': distance,
        'home_travel_times': [travel],
        'lunch_spot_distances': [[0, 0], [0, 0]],
        'lunch_spot_travel_times': [[[0, 0], [0, 0]]],
        'service_times': [0, 30],
        'earliest_start': [0, 60],
        'assigned_broker': [0, 0],
        'shift_start': [0, 0],
        'shift_end': [540, 540],
        'lunch_window': [240, 300],
        'delay_weight': 0,
        'overtime_weight': 0,
    }


def _m2(travel, distance):
    """The same visit, with one morning shift per broker and fairness turned off."""
    return {
        'num_nodes': 2,
        'num_brokers': 2,
        'shifts': [[(0, 400)], [(0, 400)]],
        'distance_matrix': [[0, 0], [0, 0]],
        'travel_times': [[[0, 0], [0, 0]]],
        'home_distances': distance,
        'home_travel_times': [travel],
        'lunch_spot_distances': distance,
        'lunch_spot_travel_times': [travel],
        'service_times': [0, 30],
        'earliest_start': [0, 60],
        'assigned_broker': [0, 0],
        'delay_weight': 0,
        'fairness_weight': 0,
    }


def _broker(model):
    """The broker whose arc into the only property is used."""
    for (i, j, k), var in model.x.items():
        if j == 1 and pyo.value(var) > 0.5:
            return pyo.value(model.route_broker[k]) if hasattr(model, 'route_broker') else k
    raise AssertionError('the visit was not served')


class TestTravelObjective(unittest.TestCase):
    def test_equal_time_picks_the_shorter_distance(self):
        travel = [[0, 10], [0, 10]]
        distance = [[0, 1], [0, 100]]
        for builder, data in ((build_model_m1, _m1(travel, distance)),
                              (build_model_m2, _m2(travel, distance))):
            with self.subTest(model=builder.__name__):
                model = builder(data)
                paid = 1 + (data['num_brokers'] if builder is build_model_m1 else 2)
                cap = paid * 100 * pyo.value(model.distance_weight)
                self.assertLess(cap, 1)
                solved, metrics = solve_model(model, solver_name='gurobi_direct', mip_gap=0.0, raw=True)
                self.assertEqual(metrics['termination_condition'], 'optimal')
                self.assertEqual(_broker(solved), 1)

    def test_one_minute_beats_any_distance(self):
        travel = [[0, 10], [0, 11]]
        distance = [[0, 100], [0, 1]]
        for builder, data in ((build_model_m1, _m1(travel, distance)),
                              (build_model_m2, _m2(travel, distance))):
            with self.subTest(model=builder.__name__):
                model = builder(data)
                solved, metrics = solve_model(model, solver_name='gurobi_direct', mip_gap=0.0, raw=True)
                self.assertEqual(metrics['termination_condition'], 'optimal')
                self.assertEqual(_broker(solved), 1)


if __name__ == '__main__':
    unittest.main()
