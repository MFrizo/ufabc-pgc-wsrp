"""
Checks the fleet drawn with num_brokers="auto": between the fewest brokers the visits need
and the most the solver takes, without changing what the schedule's brokers do.
"""

import unittest

import pyomo.environ as pyo

from src.core.data_generator import AUTO_BROKERS, MAX_ROUTING_ARCS, generate_wsrp_instance, max_fleet
from src.core.listings import load_instance
from src.models import INSTANCE_SETTINGS
from src.models.model_7 import build_model_m7
from src.solvers.engine import solve_model

SCHEDULE_KEYS = ('earliest_start', 'latest_start', 'fixed_visits', 'assigned_broker', 'service_times',
                 'coordinates', 'distance_matrix')


def auto(model, num_properties, seed):
    return generate_wsrp_instance(num_properties=num_properties, random_seed=seed,
                                  **{**INSTANCE_SETTINGS[model], 'num_brokers': AUTO_BROKERS})


def fixed(model, num_properties, seed, num_brokers):
    return generate_wsrp_instance(num_properties=num_properties, random_seed=seed,
                                  **{**INSTANCE_SETTINGS[model], 'num_brokers': num_brokers})


class AutoBrokersTest(unittest.TestCase):
    def test_fleet_lies_between_the_fewest_needed_and_the_most_viable(self):
        for model in INSTANCE_SETTINGS:
            for num_properties in (5, 8, 12):
                for seed in (1, 17, 42):
                    data = auto(model, num_properties, seed)
                    self.assertLessEqual(data['schedule_brokers'], data['num_brokers'])
                    self.assertLessEqual(data['num_brokers'], data['max_brokers'])
                    settings = INSTANCE_SETTINGS[model]
                    self.assertEqual(data['max_brokers'],
                                     max_fleet(num_properties, data['schedule_brokers'], settings.get('days_off', 0),
                                               settings.get('max_routing_arcs', MAX_ROUTING_ARCS)))

    def test_fewer_brokers_than_the_schedule_do_not_fit_the_day(self):
        for model in ('m2', 'm7', 'm8'):
            for seed in (1, 17, 42):
                data = auto(model, 12, seed)
                fewer = data['schedule_brokers'] - 1
                if fewer <= INSTANCE_SETTINGS[model].get('days_off', 0):
                    continue
                settings = INSTANCE_SETTINGS[model]
                day = settings.get('max_day_length') or settings.get('horizon', 600)
                try:
                    smaller = fixed(model, 12, seed, fewer)
                except ValueError:
                    continue
                self.assertFalse(not settings.get('split_shifts') and smaller['latest_start'][0] <= day)

    def test_schedule_brokers_keep_their_data(self):
        for model in ('m2', 'm7', 'm8'):
            for seed in range(1, 11):
                data = auto(model, 5, seed)
                schedule = fixed(model, 5, seed, data['schedule_brokers'])
                k = data['schedule_brokers']
                for key in SCHEDULE_KEYS:
                    self.assertEqual(data[key], schedule[key], key)
                self.assertEqual(data['home_coordinates'][:k], schedule['home_coordinates'])
                self.assertEqual(data['lunch_spot_coordinates'][:k], schedule['lunch_spot_coordinates'])
                self.assertEqual(data['shifts'][:k], schedule['shifts'])
                for key in ('home_coordinates', 'home_distances', 'lunch_spot_coordinates', 'shifts',
                            'shift_start', 'shift_end'):
                    self.assertEqual(len(data[key]), data['num_brokers'], key)

    def test_fleet_is_random_but_reproducible(self):
        fleets = {auto('m2', 5, seed)['num_brokers'] for seed in range(1, 21)}
        self.assertGreater(len(fleets), 1)
        self.assertEqual(auto('m7', 8, 17), auto('m7', 8, 17))

    def test_max_fleet_respects_the_solver_budget(self):
        for num_properties in (3, 5, 10, 20, 40):
            for schedule_brokers in (1, 2, 4):
                if schedule_brokers > num_properties:
                    continue
                most = max_fleet(num_properties, schedule_brokers)
                self.assertGreaterEqual(most, schedule_brokers)
                self.assertLessEqual(most, num_properties)
                if most > schedule_brokers:
                    self.assertLessEqual(most * (num_properties + 1) * num_properties, MAX_ROUTING_ARCS)

    def test_fixed_fleet_is_unchanged(self):
        data = load_instance("synthetic", "m7", num_properties=5, random_seed=17)
        self.assertEqual(data['num_brokers'], INSTANCE_SETTINGS['m7']['num_brokers'])
        self.assertNotIn('schedule_brokers', data)

    def test_m7_solves_a_real_neighborhood_with_an_auto_fleet(self):
        data = load_instance("real", "m7", num_properties=10, random_seed=17, num_brokers=AUTO_BROKERS,
                             city="São Paulo", neighborhood="Moema")

        solved_model, metrics = solve_model(build_model_m7(data), solver_name="gurobi_direct", mip_gap=0.0, raw=True)
        self.assertEqual(metrics["termination_condition"], "optimal")
        used = round(sum(pyo.value(solved_model.y[k]) for k in solved_model.K))
        self.assertLessEqual(used, data['num_brokers'])

    def test_invalid_fleets_are_rejected(self):
        for invalid in (0, -1, "many", 2.5, True):
            with self.assertRaises(ValueError):
                load_instance("synthetic", "m7", num_brokers=invalid)


if __name__ == "__main__":
    unittest.main()
