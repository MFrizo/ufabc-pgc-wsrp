"""
Checks that the brokers of a real instance live at random places inside its city.
"""

import math
import unittest

import numpy as np

from src.core.data_generator import AUTO_BROKERS, _points_in_polygon
from src.core.listings import MAP_CENTER, MAP_UNITS_PER_KM, _convex_hull, _map_projection, load_instance, select_listings
from src.utils.real_catalog import REAL_CATALOG, clean_real_catalog

CITY, NEIGHBORHOOD = "São Paulo", "Moema"


def _inside(point, hull, tolerance=1e-6):
    """Whether a point lies inside a counter-clockwise convex hull."""
    return all((end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])
               >= -tolerance * math.hypot(end[0] - start[0], end[1] - start[1])
               for start, end in zip(hull, hull[1:] + hull[:1]))


class CityBrokerHomesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = clean_real_catalog(REAL_CATALOG)

    def _city_hull(self, data):
        houses = data["listings"]
        to_map = _map_projection([house["lat"] for house in houses], [house["lon"] for house in houses])
        in_city = self.catalog.loc[self.catalog["city"].eq(CITY)]
        return _convex_hull([to_map(lat, lon) for lat, lon in zip(in_city["lat"], in_city["lon"])])

    def test_homes_are_inside_the_city(self):
        for seed in range(1, 6):
            data = load_instance("real", "m7", num_properties=6, random_seed=seed, num_brokers=4,
                                 city=CITY, neighborhood=NEIGHBORHOOD)
            hull = self._city_hull(data)
            for home in data["home_coordinates"]:
                self.assertTrue(_inside(home, hull), f"seed {seed}: home {home} is outside {CITY}")

    def test_homes_spread_over_the_city_not_the_neighborhood(self):
        moema = select_listings(self.catalog, CITY, NEIGHBORHOOD)
        to_map = _map_projection(moema["lat"].tolist(), moema["lon"].tolist())
        moema_radius = max(math.dist(MAP_CENTER, to_map(lat, lon)) for lat, lon in zip(moema["lat"], moema["lon"]))
        farthest = max(math.dist(MAP_CENTER, home)
                       for seed in range(1, 6)
                       for home in load_instance("real", "m7", num_properties=6, random_seed=seed, num_brokers=4,
                                                 city=CITY, neighborhood=NEIGHBORHOOD)["home_coordinates"])
        self.assertGreater(farthest, 3 * moema_radius)
        self.assertGreater(farthest / MAP_UNITS_PER_KM, 10)

    def test_home_distances_follow_the_homes(self):
        data = load_instance("real", "m7", num_properties=6, random_seed=17, city=CITY, neighborhood=NEIGHBORHOOD)
        for home, distances in zip(data["home_coordinates"], data["home_distances"]):
            self.assertEqual(distances, [round(math.dist(home, node), 2) for node in data["coordinates"]])

    def test_auto_fleet_homes_are_inside_the_city_and_keep_the_schedule_ones(self):
        data = load_instance("real", "m7", num_properties=8, random_seed=17, num_brokers=AUTO_BROKERS,
                             city=CITY, neighborhood=NEIGHBORHOOD)
        schedule = load_instance("real", "m7", num_properties=8, random_seed=17,
                                 num_brokers=data["schedule_brokers"], city=CITY, neighborhood=NEIGHBORHOOD)
        hull = self._city_hull(data)

        self.assertEqual(len(data["home_coordinates"]), data["num_brokers"])
        self.assertEqual(data["home_coordinates"][:data["schedule_brokers"]], schedule["home_coordinates"])
        self.assertTrue(all(_inside(home, hull) for home in data["home_coordinates"]))

    def test_points_are_uniform_over_the_polygon(self):
        square = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
        points = np.array(_points_in_polygon(np.random.default_rng(0).random((20000, 3)), square))

        self.assertTrue(((points >= 0) & (points <= 10)).all())
        self.assertTrue(np.allclose(points.mean(axis=0), [5, 5], atol=0.1))
        self.assertAlmostEqual(float((points[:, 0] < 5).mean()), 0.5, delta=0.02)
        self.assertAlmostEqual(float((points[:, 1] < 5).mean()), 0.5, delta=0.02)

    def test_points_of_a_polygon_without_area_lie_on_its_segment(self):
        draws = np.random.default_rng(0).random((50, 3))

        self.assertEqual(_points_in_polygon(draws, [[3.0, 4.0]]), [[3.0, 4.0]] * 50)
        for x, y in _points_in_polygon(draws, [[0.0, 0.0], [2.0, 2.0]]):
            self.assertAlmostEqual(x, y)
            self.assertTrue(0 <= x <= 2)

    def test_convex_hull_drops_inner_and_collinear_points(self):
        points = [[0, 0], [2, 0], [4, 0], [4, 4], [0, 4], [1, 1], [2, 3], [0, 0]]
        self.assertEqual(_convex_hull(points), [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0]])


if __name__ == "__main__":
    unittest.main()
