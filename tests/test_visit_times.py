"""
Checks the share of visits at a strict time, and that those times are uniformly distributed
over each broker's free time.
"""

import math
import unittest

import numpy as np

from src.core.data_generator import _place_visits, generate_wsrp_instance
from src.core.listings import load_instance
from src.models import BUILDERS, INSTANCE_SETTINGS, STRICT_TIME_MODELS
from src.solvers.engine import solve_model
from src.utils.logger import project_logger

SLACK = 300


def _starts(num_visits: int, draws: int, service: int = 0) -> np.ndarray:
    """Start times of num_visits visits, with no travel, in a day of SLACK free minutes, for many draws."""
    rng = np.random.default_rng(0)
    nodes = list(range(1, num_visits + 1))
    no_travel = [[0] * (num_visits + 1) for _ in range(num_visits + 1)]
    services = [0] + [service] * num_visits
    day_end = SLACK + service * num_visits
    starts = np.empty((draws, num_visits))
    for draw in range(draws):
        reference_start = [0] * (num_visits + 1)
        _place_visits(rng, nodes, [0] * (num_visits + 1), no_travel, services, 0, day_end, reference_start)
        starts[draw] = reference_start[1:]
    return starts


class VisitTimesTest(unittest.TestCase):
    def test_share_of_strict_visits_follows_the_ratio(self):
        for ratio in (0.0, 0.3, 0.5, 1.0):
            data = generate_wsrp_instance(num_properties=10, random_seed=3, num_brokers=3, fixed_ratio=ratio)

            self.assertEqual(len(data['fixed_visits']), round(ratio * 10))
            for node in range(1, 11):
                if node in data['fixed_visits']:
                    self.assertEqual(data['earliest_start'][node], data['latest_start'][node])
                else:
                    self.assertEqual(data['earliest_start'][node], 0)
                    self.assertEqual(data['latest_start'][node], data['latest_start'][0] - data['service_times'][node])

    def test_one_visit_starts_uniformly_over_the_free_time(self):
        starts = np.sort(_starts(1, 4000)[:, 0])
        self.assertTrue(((starts >= 0) & (starts <= SLACK)).all())

        # Kolmogorov-Smirnov distance to U(0, SLACK), against its 1% critical value
        empirical = np.arange(1, len(starts) + 1) / len(starts)
        distance = np.max(np.abs(empirical - (starts + 0.5) / SLACK))
        self.assertLess(distance, 1.63 / math.sqrt(len(starts)))

    def test_several_visits_are_uniform_order_statistics(self):
        num_visits, draws = 4, 4000
        idle = _starts(num_visits, draws, service=30) - 30 * np.arange(num_visits)

        # The k-th of n sorted U(0, SLACK) draws has mean k / (n + 1) * SLACK
        expected = np.arange(1, num_visits + 1) / (num_visits + 1) * SLACK
        self.assertTrue(np.allclose(idle.mean(axis=0), expected, atol=4))
        self.assertTrue((np.diff(idle, axis=1) >= -1).all())

    def test_the_last_visit_always_ends_by_the_end_of_the_day(self):
        starts = _starts(5, 1000, service=40)
        self.assertTrue((starts[:, -1] + 40 <= SLACK + 5 * 40).all())

    def test_ratio_overrides_the_model_setting(self):
        for dataset, place in (("synthetic", {}), ("real", {"city": "São Paulo", "neighborhood": "Moema"})):
            data = load_instance(dataset, "m2", num_properties=6, random_seed=3, fixed_ratio=0.5, **place)
            self.assertEqual(len(data['fixed_visits']), 3)
        self.assertEqual(len(load_instance("synthetic", "m2", num_properties=6, random_seed=3)['fixed_visits']), 6)

    def test_ratio_outside_zero_to_one_is_rejected(self):
        for ratio in (-0.1, 1.5):
            with self.assertRaises(ValueError):
                load_instance("synthetic", "m2", fixed_ratio=ratio)

    def test_strict_time_models_warn_and_ignore_the_ratio(self):
        for model in STRICT_TIME_MODELS:
            with self.assertLogs(project_logger, level="WARNING") as logs:
                data = load_instance("synthetic", model, num_properties=6, random_seed=3, fixed_ratio=0.5)

            self.assertIn("strict time", logs.output[0])
            self.assertEqual(data, load_instance("synthetic", model, num_properties=6, random_seed=3))

    def test_models_with_time_windows_solve_a_mixed_instance(self):
        for model in ('m1', 'm2', 'm3', 'm4', 'm5', 'm6'):
            data = load_instance("synthetic", model, num_properties=6, random_seed=3, fixed_ratio=0.5)
            _, metrics = solve_model(BUILDERS[model](data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
            self.assertEqual(metrics['termination_condition'], 'optimal', model)

    def test_every_model_keeps_its_own_ratio_by_default(self):
        for model, settings in INSTANCE_SETTINGS.items():
            data = load_instance("synthetic", model, num_properties=5, random_seed=3)
            self.assertEqual(len(data['fixed_visits']), round(settings.get('fixed_ratio', 0.2) * 5))


if __name__ == "__main__":
    unittest.main()
