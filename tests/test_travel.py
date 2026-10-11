"""
Checks the detoured straight-line distances of a synthetic instance and the street
distances and congestion-scaled travel times of São Paulo instances.
"""

import json
import math
import unittest

import numpy as np

from src.core.data_generator import generate_wsrp_instance
from src.core.listings import _house_graph, load_instance, select_listings
from src.core.travel import (COORD_DECIMALS, DETOUR_PATH, DETOUR_SAMPLE_SEED, INDEXED_CITY,
                             WHOLE_CITY_SAMPLE, congestion_factors, detour_factor, indexed_coordinates,
                             straight_meters, travel_minutes)
from src.utils.real_catalog import REAL_CATALOG, clean_real_catalog
from src.models import NORMAL_SPEED, RUSH_HOURS
from src.models.model_0_0 import build_model_m0_0


def _sao_paulo(model: str) -> dict:
    return load_instance("real", model, num_properties=WHOLE_CITY_SAMPLE["num_properties"],
                         random_seed=WHOLE_CITY_SAMPLE["random_seed"], city=WHOLE_CITY_SAMPLE["city"])


class TravelTest(unittest.TestCase):
    def test_synthetic_distance_is_straight_line_times_the_detour_factor(self):
        data = generate_wsrp_instance(num_properties=5, random_seed=42, num_brokers=2, speed_profile=RUSH_HOURS)
        again = generate_wsrp_instance(num_properties=5, random_seed=42, num_brokers=2, speed_profile=RUSH_HOURS)
        factor = detour_factor()

        self.assertEqual(data, again)
        self.assertNotIn("duration_matrix", data)
        self.assertGreater(factor, 1)
        for i, origin in enumerate(data["coordinates"]):
            for j, destination in enumerate(data["coordinates"]):
                if i == j:
                    self.assertEqual(data["distance_matrix"][i][j], 0)
                else:
                    self.assertEqual(data["distance_matrix"][i][j],
                                     round(math.dist(origin, destination) * factor, 2))
        for home, distances in zip(data["home_coordinates"], data["home_distances"]):
            self.assertEqual(distances, [round(math.dist(home, node) * factor, 2) for node in data["coordinates"]])
        for period, (_, speed) in enumerate(RUSH_HOURS):
            for row, distances in zip(data["travel_times"][period], data["distance_matrix"]):
                self.assertEqual(row, [math.ceil(distance / speed) for distance in distances])

    def test_detour_factor_is_the_median_of_the_cached_pairs(self):
        payload = json.loads(DETOUR_PATH.read_text(encoding="utf-8"))
        ratios = [pair["road_m"] / pair["straight_m"] for pair in payload["pairs"]]

        self.assertEqual(payload["seed"], DETOUR_SAMPLE_SEED)
        self.assertEqual(payload["city"], "São Paulo")
        self.assertGreaterEqual(len(ratios), 10)
        self.assertEqual(payload["factor"], round(float(np.median(ratios)), 4))
        self.assertEqual(detour_factor(), payload["factor"])
        for pair in payload["pairs"]:
            self.assertEqual(pair["straight_m"], straight_meters(pair["from"], pair["to"]))

    def test_cached_real_instance_uses_the_street_matrix_and_congestion(self):
        data = _sao_paulo("m0.5")
        again = _sao_paulo("m0.5")
        factors = congestion_factors("São Paulo", RUSH_HOURS)

        self.assertEqual(data["distance_matrix"], again["distance_matrix"])
        self.assertEqual(data["travel_times"], again["travel_times"])
        self.assertEqual(data["city"], "São Paulo")
        self.assertEqual(data["period_starts"], [0, 120, 540])
        self.assertIn("duration_matrix", data)
        for period, factor in enumerate(factors):
            for durations, times in zip(data["duration_matrix"], data["travel_times"][period]):
                self.assertEqual(times, [travel_minutes(duration, factor) for duration in durations])
        self.assertTrue(any(data["distance_matrix"][i][j] != data["distance_matrix"][j][i]
                            for i in range(data["num_nodes"]) for j in range(i)))
        straight = [[0.0 if i == j else round(math.dist(a, b), 2)
                     for j, b in enumerate(data["coordinates"])]
                    for i, a in enumerate(data["coordinates"])]
        self.assertNotEqual(data["distance_matrix"], straight)

    def test_single_period_real_instance_uses_the_midday_factor(self):
        rush = _sao_paulo("m0.5")
        normal = _sao_paulo("m1")

        self.assertEqual(congestion_factors("São Paulo", NORMAL_SPEED), [congestion_factors("São Paulo", RUSH_HOURS)[1]])
        self.assertEqual(normal["distance_matrix"], rush["distance_matrix"])
        self.assertEqual(normal["travel_times"], [rush["travel_times"][1]])

    def test_constant_travel_time_ignores_the_street_duration(self):
        data = _sao_paulo("m0.1")

        self.assertIn("duration_matrix", data)
        self.assertEqual(data["travel_time"], 30)
        self.assertTrue(all(time in (0, 30) for row in data["travel_times"][0] for time in row))

    def test_whole_city_sample_uses_the_street_matrix(self):
        data = load_instance("real", "m1", num_properties=WHOLE_CITY_SAMPLE["num_properties"],
                             random_seed=WHOLE_CITY_SAMPLE["random_seed"], city=WHOLE_CITY_SAMPLE["city"])

        self.assertIn("duration_matrix", data)
        self.assertGreater(len({listing["district"] for listing in data["listings"]}), 1)
        self.assertGreater(max(max(row) for row in data["distance_matrix"]), 40)

    def test_the_index_covers_every_sao_paulo_listing(self):
        catalog = select_listings(clean_real_catalog(str(REAL_CATALOG)), INDEXED_CITY)
        listed = {(round(float(lat), COORD_DECIMALS), round(float(lon), COORD_DECIMALS))
                  for lat, lon in zip(catalog["lat"], catalog["lon"])}

        self.assertEqual(indexed_coordinates(), listed)

    def test_any_sample_of_the_city_uses_the_street_index(self):
        one = load_instance("real", "m1", num_properties=6, random_seed=99, city="São Paulo")
        other = load_instance("real", "m0.5", num_properties=4, random_seed=1, city="São Paulo")

        self.assertIn("duration_matrix", one)
        self.assertIn("duration_matrix", other)
        self.assertGreater(len({listing["district"] for listing in one["listings"]}), 1)
        self.assertGreater(len({listing["district"] for listing in other["listings"]}), 1)

    def test_a_one_way_pocket_is_not_a_direct_arc(self):
        dead_end = (-23.55865, -46.600142)
        pockets = {dead_end, (-23.62386, -46.719393), (-23.622656, -46.716999), (-23.620095, -46.71745)}
        reachable = min(indexed_coordinates() - pockets)
        graph = _house_graph([dead_end[0], reachable[0]], [dead_end[1], reachable[1]])
        blocked = set(graph["blocked_arcs"])

        self.assertIn((1, 2), blocked)
        self.assertNotIn((2, 1), blocked)

        data = load_instance("synthetic", "m0.0", num_properties=3, random_seed=1)
        data["blocked_arcs"] = [(1, 2)]
        model = build_model_m0_0(data)
        self.assertTrue(model.x[1, 2].fixed)
        self.assertEqual(model.x[1, 2].value, 0)
        self.assertFalse(model.x[2, 1].fixed)

    def test_a_city_without_an_index_keeps_straight_line_distance(self):
        data = load_instance("real", "m0.5", num_properties=4, random_seed=1, city="Rio de Janeiro")
        coordinates = data["coordinates"]

        self.assertNotIn("duration_matrix", data)
        for i, origin in enumerate(coordinates):
            for j, destination in enumerate(coordinates):
                expected = 0.0 if i == j else round(math.dist(origin, destination), 2)
                self.assertEqual(data["distance_matrix"][i][j], expected)


if __name__ == "__main__":
    unittest.main()
