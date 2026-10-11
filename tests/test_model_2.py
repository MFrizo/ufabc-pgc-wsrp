"""
Checks the workload term of M2: the longest time a working broker is out.

Two properties sit next to broker 1 and a long way from broker 2. Travel times equal
the distances, so travel time alone gives both visits to broker 1. Each visit takes long enough that splitting them
shortens the busiest day, and the fairness weight does that split. Broker 3 is off.
"""

import unittest

import pyomo.environ as pyo

from src.models.model_2 import build_model_m2
from src.solvers.engine import solve_model


def _instance():
    """Two visits broker 1 can do cheaply, and a third broker with the day off."""
    near = [0, 1, 6]
    far = [0, 25, 25]
    between = [
        [0, 0, 0],
        [0, 0, 5],
        [0, 5, 0],
    ]
    return {
        'num_nodes': 3,
        'num_brokers': 3,
        'shifts': [[(0, 400), (450, 600)], [(0, 400), (450, 600)], []],
        'distance_matrix': between,
        'travel_times': [between],
        'home_distances': [near, far, near],
        'lunch_spot_distances': [near, far, near],
        'home_travel_times': [[near, far, near]],
        'lunch_spot_travel_times': [[near, far, near]],
        'service_times': [0, 60, 60],
        'earliest_start': [0, 60, 140],
        'assigned_broker': [0, 0, 0],
    }


def _visits_of(model):
    """Properties served by each broker."""
    served = {k: [] for k in model.K}
    for i, j, r in model.ARCS:
        if i in model.C and pyo.value(model.x[i, j, r]) > 0.5:
            served[pyo.value(model.route_broker[r])].append(i)
    return served


def _solve(data):
    solved, metrics = solve_model(build_model_m2(data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
    return solved, metrics


class Model2FairnessTest(unittest.TestCase):
    def test_without_the_fairness_weight_one_broker_takes_both_visits(self):
        model, metrics = _solve({**_instance(), 'fairness_weight': 0})
        self.assertEqual(metrics["termination_condition"], "optimal")

        served = _visits_of(model)
        self.assertEqual(served[1], [1, 2])
        self.assertEqual(served[2], [])
        self.assertEqual(served[3], [])
        self.assertEqual(pyo.value(model.workload[3]), 0)

    def test_the_fairness_weight_splits_the_visits(self):
        model, metrics = _solve(_instance())
        self.assertEqual(metrics["termination_condition"], "optimal")

        served = _visits_of(model)
        self.assertEqual(sorted(served[1] + served[2]), [1, 2])
        self.assertEqual(len(served[1]), 1)
        self.assertEqual(len(served[2]), 1)
        self.assertEqual(served[3], [])
        self.assertEqual(pyo.value(model.workload[3]), 0)
        self.assertAlmostEqual(pyo.value(model.max_workload),
                               max(pyo.value(model.workload[1]), pyo.value(model.workload[2])), places=4)
        self.assertLess(pyo.value(model.max_workload), 120)

    def test_a_generated_instance_still_solves(self):
        from src.core.listings import load_instance

        data = load_instance("synthetic", "m2", num_properties=4, random_seed=8)
        _, metrics = _solve(data)
        self.assertEqual(metrics["termination_condition"], "optimal")


if __name__ == "__main__":
    unittest.main()
