"""The hidden schedule stays on unless the caller turns it off."""

import unittest

from src.core.data_generator import generate_wsrp_instance
from src.core.listings import load_instance
from src.models import BUILDERS, INSTANCE_SETTINGS
from src.solvers.engine import solve_model


def _overfull(**overrides):
    """An M1-shaped day one broker cannot pack into the longest working day."""
    settings = dict(INSTANCE_SETTINGS['m1'])
    settings.update(num_brokers=1, num_properties=12, random_seed=1, hidden_schedule=True)
    settings.update(overrides)
    num_properties = settings.pop('num_properties')
    random_seed = settings.pop('random_seed')
    return generate_wsrp_instance(num_properties=num_properties, random_seed=random_seed, **settings)


class HiddenScheduleTest(unittest.TestCase):
    def test_default_refuses_a_day_the_visits_cannot_pack(self):
        with self.assertRaises(ValueError):
            _overfull()

    def test_off_returns_the_same_instance_and_reaches_the_solver(self):
        first = _overfull(hidden_schedule=False)
        second = _overfull(hidden_schedule=False)

        self.assertFalse(first['hidden_schedule'])
        self.assertEqual(len(first['fixed_visits']), first['num_nodes'] - 1)
        self.assertEqual(first['earliest_start'], second['earliest_start'])
        self.assertTrue(all(start == end for start, end in zip(first['earliest_start'][1:], first['latest_start'][1:])))
        self.assertEqual(set(first['assigned_broker']), {0})

        model = BUILDERS['m1'](first)
        _, metrics = solve_model(model, mip_gap=0, raw=False, time_limit=30)

        self.assertEqual(metrics['termination_condition'], 'infeasible')

    def test_load_instance_keeps_the_schedule_on_unless_asked(self):
        on = load_instance('synthetic', 'm1', num_properties=5, random_seed=8)
        off = load_instance('synthetic', 'm1', num_properties=5, random_seed=8, hidden_schedule=False)

        self.assertTrue(on['hidden_schedule'])
        self.assertFalse(off['hidden_schedule'])
        self.assertNotEqual(on['earliest_start'], off['earliest_start'])


if __name__ == '__main__':
    unittest.main()
