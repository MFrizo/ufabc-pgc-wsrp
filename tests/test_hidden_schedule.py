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
    def test_raise_on_fit_failure_refuses_a_day_the_visits_cannot_pack(self):
        with self.assertRaises(ValueError):
            _overfull(raise_on_fit_failure=True)

    def test_default_hidden_schedule_passes_overfull_day_and_proves_infeasible(self):
        instance = _overfull()
        self.assertTrue(instance['hidden_schedule'])
        self.assertTrue(instance['schedule_overflow'])
        model = BUILDERS['m1'](instance)
        _, metrics = solve_model(model, mip_gap=0, raw=False, time_limit=30)
        self.assertEqual(metrics['termination_condition'], 'infeasible')

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

    def test_duration_constraints_prove_overfull_fleet_infeasible_in_presolve(self):
        import pyomo.environ as pyo

        for variant, per_route_attr in [
            ('m1', 'route_duration_constraint'),
            ('m1.a', 'route_duration_constraint'),
            ('m2', 'shift_duration_constraint'),
            ('m2.a', 'shift_duration_constraint'),
            ('m3', 'route_duration_constraint'),
            ('m3.a', 'route_duration_constraint'),
        ]:
            with self.subTest(model=variant):
                settings = dict(INSTANCE_SETTINGS[variant])
                settings.update(num_brokers=2, hidden_schedule=False)
                data = generate_wsrp_instance(num_properties=12, random_seed=1, **settings)
                for i in range(1, 13):
                    data['service_times'][i] = 120.0

                model = BUILDERS[variant](data)
                self.assertTrue(hasattr(model, per_route_attr))
                self.assertTrue(hasattr(model, 'fleet_duration_constraint'))

                solver = pyo.SolverFactory('gurobi_direct')
                result = solver.solve(model, tee=False)
                self.assertEqual(str(result.solver.termination_condition), 'infeasible')
                self.assertEqual(solver._solver_model.IterCount, 0.0)
                self.assertEqual(solver._solver_model.NodeCount, 0.0)


if __name__ == '__main__':
    unittest.main()

