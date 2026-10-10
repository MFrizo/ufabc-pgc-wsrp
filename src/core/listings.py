"""
Module: listings
Description: Builds the instance a model runs on, from the synthetic generator or from the
             real rental catalog of src.utils.real_catalog. A real call keeps one city, and
             optionally one neighborhood of it, then samples that slice: the national file
             is too large for the solver, and a broker does not travel from one city to
             another. The graph
             of the houses is built from listing.address.point.lat and
             listing.address.point.lon, and each visit lasts longer the larger the listing's
             usable area. Each broker's home is drawn at random inside the city, the convex
             hull of its listings. Every other feature (lunch spots, time windows,
             assignments) still comes from the generator.
"""

import math
from typing import Any, Callable, Optional, Union

import numpy as np
import pandas as pd

from src.core.data_generator import AUTO_BROKERS, generate_wsrp_instance
from src.models import INSTANCE_SETTINGS, SINGLE_BROKER_MODELS, STRICT_TIME_MODELS
from src.utils.logger import project_logger
from src.utils.real_catalog import (KM_PER_DEGREE_LAT, KM_PER_DEGREE_LON, REAL_CATALOG, REAL_CATALOG_SOURCE,
                                    clean_real_catalog)

DATASETS = ("synthetic", "real")

# The generator draws the city on a 100x100 map, about 25 km across, so one kilometer is
# 4 units and a speed of 2 units per minute is about 30 km/h. The houses keep that scale,
# around the agency at the center of the map.
MAP_UNITS_PER_KM = 4.0
MAP_CENTER = (50.0, 50.0)


def load_instance(dataset: str, model_version: str, num_properties: int = 5, random_seed: int = 42,
                  num_brokers: Optional[Union[int, str]] = None, city: Optional[str] = None,
                  neighborhood: Optional[str] = None, fixed_ratio: Optional[float] = None) -> dict[str, Any]:
    """
    Builds the instance a model runs on, either from the generator or from the real catalog.

    Args:
        dataset (str): "synthetic" or "real".
        model_version (str): Key of src.models.BUILDERS. Selects that model's INSTANCE_SETTINGS.
        num_properties (int): Number of properties to visit.
        random_seed (int): Seed of the sample and of every generated feature.
        num_brokers (Optional[Union[int, str]]): Number of brokers |K|, read from M2 onwards;
            SINGLE_BROKER_MODELS warn and ignore it. AUTO_BROKERS draws it between the fewest
            brokers the visits need and the most the solver can take. None keeps the model's
            own setting.
        city (Optional[str]): City of a real instance. Required when dataset is "real".
        neighborhood (Optional[str]): Neighborhood of a real instance, inside that city. None
            samples the whole city.
        fixed_ratio (Optional[float]): Share of the visits with a strict start time, from 0 to
            1; the others may start at any time of the day. STRICT_TIME_MODELS warn and ignore
            it. None keeps the model's own setting.

    Returns:
        dict[str, Any]: The instance payload. A real instance also carries 'listings'.

    Raises:
        ValueError: If dataset is unknown, num_brokers is neither a positive integer nor
            AUTO_BROKERS, fixed_ratio is outside [0, 1], a real call omits the city, or the
            city or neighborhood cannot supply the sample.
    """
    if dataset not in DATASETS:
        raise ValueError(f"dataset must be one of: {', '.join(DATASETS)}.")
    if num_brokers is not None and num_brokers != AUTO_BROKERS and (
            isinstance(num_brokers, bool) or not isinstance(num_brokers, int) or num_brokers < 1):
        raise ValueError(f"num_brokers must be a positive integer or {AUTO_BROKERS!r}.")
    if num_brokers is not None and model_version in SINGLE_BROKER_MODELS:
        project_logger.warning(f"{model_version} routes a single broker; ignoring num_brokers={num_brokers!r}.")
        num_brokers = None
    if fixed_ratio is not None and not 0 <= fixed_ratio <= 1:
        raise ValueError(f"fixed_ratio must be between 0 and 1, not {fixed_ratio}.")
    if fixed_ratio is not None and model_version in STRICT_TIME_MODELS:
        project_logger.warning(f"{model_version} books every visit at a strict time; ignoring fixed_ratio={fixed_ratio}.")
        fixed_ratio = None

    instance_settings = dict(INSTANCE_SETTINGS[model_version])
    if num_brokers is not None:
        instance_settings['num_brokers'] = num_brokers
    if fixed_ratio is not None:
        instance_settings['fixed_ratio'] = fixed_ratio

    if dataset == "synthetic":
        return generate_wsrp_instance(num_properties=num_properties, random_seed=random_seed, **instance_settings)

    if not city or not city.strip():
        raise ValueError(
            "A real instance needs a city. "
            "The full catalog is too large for the solver, and a broker does not travel between cities."
        )
    project_logger.info(f"Real listings are a snapshot of a Brazilian real estate company: {REAL_CATALOG_SOURCE}")
    return instance_from_catalog(city.strip(), neighborhood.strip() if neighborhood and neighborhood.strip() else None,
                                 num_properties=num_properties, random_seed=random_seed, **instance_settings)


def instance_from_catalog(city: str, neighborhood: Optional[str] = None, num_properties: int = 5,
                          random_seed: int = 42, **instance_settings: Any) -> dict[str, Any]:
    """
    Samples listings of one city, or of one neighborhood of it, from REAL_CATALOG and builds
    the instance on them.

    Args:
        city (str): City the sample is drawn from.
        neighborhood (Optional[str]): Neighborhood of that city the sample is drawn from. None
            draws it from the whole city.
        num_properties (int): How many listings become visits.
        random_seed (int): Seed of the sample and of every generated feature.
        **instance_settings: Settings of generate_wsrp_instance, such as a model's INSTANCE_SETTINGS.

    Returns:
        dict[str, Any]: The payload of generate_wsrp_instance on the sampled houses, plus
            'listings': the catalog row behind each node from 1 on.

    Raises:
        ValueError: If the city or the neighborhood has no listings, or fewer than num_properties.
    """
    if num_properties < 1:
        raise ValueError("num_properties must be at least 1.")

    full_catalog = clean_real_catalog(str(REAL_CATALOG))
    catalog = select_listings(full_catalog, city, neighborhood)
    place = f"{neighborhood}, {city}" if neighborhood else city
    if num_properties > len(catalog):
        raise ValueError(f"{place} has {len(catalog)} listings, fewer than {num_properties}.")

    project_logger.info(f"Sampling {num_properties} of {len(catalog)} listings in {place}.")
    rng = np.random.default_rng(random_seed)
    chosen = catalog.iloc[rng.choice(len(catalog), size=num_properties, replace=False)].reset_index(drop=True)

    to_map = _map_projection(chosen["lat"].tolist(), chosen["lon"].tolist())
    in_city = full_catalog.loc[full_catalog["city"].eq(city)]
    project_logger.info(f"Drawing the broker homes inside {city}, the area of its {len(in_city)} listings.")
    data_payload = generate_wsrp_instance(num_properties=num_properties, random_seed=random_seed,
                                          graph=_house_graph(chosen["lat"].tolist(), chosen["lon"].tolist()),
                                          areas=chosen["area"].tolist(),
                                          home_region=_convex_hull([to_map(lat, lon) for lat, lon
                                                                    in zip(in_city["lat"], in_city["lon"])]),
                                          **instance_settings)
    data_payload['listings'] = [_listing_record(node, row)
                                for node, row in enumerate(chosen.itertuples(index=False), start=1)]
    return data_payload


def select_listings(catalog: pd.DataFrame, city: str, neighborhood: Optional[str] = None) -> pd.DataFrame:
    """
    Keeps the listings of one city, or of one neighborhood of it.

    Args:
        catalog (pd.DataFrame): Cleaned catalog, as returned by clean_real_catalog.
        city (str): City to keep.
        neighborhood (Optional[str]): Neighborhood to keep inside that city. None keeps the
            whole city.

    Returns:
        pd.DataFrame: The listings kept, in catalog order.

    Raises:
        ValueError: If the city, or the neighborhood inside it, has no listings.
    """
    in_city = catalog.loc[catalog["city"].eq(city)]
    if in_city.empty:
        raise ValueError(f"The real catalog has no listings in {city}.")
    if neighborhood is None:
        return in_city.reset_index(drop=True)
    in_neighborhood = in_city.loc[in_city["district"].eq(neighborhood)]
    if in_neighborhood.empty:
        raise ValueError(f"The real catalog has no listings in {neighborhood}, {city}.")
    return in_neighborhood.reset_index(drop=True)


def _house_graph(latitudes: list[float], longitudes: list[float]) -> dict[str, Any]:
    """
    Places the agency and the houses on the generator's map from listing.address.point.lat
    and listing.address.point.lon.

    The agency (node 0) sits at the center of the map, on the centroid of the houses. Each
    house is its equirectangular offset from that centroid, MAP_UNITS_PER_KM units per
    kilometer, east along x and north along y.

    Args:
        latitudes (list[float]): Latitude of each house, in node order from 1 on.
        longitudes (list[float]): Longitude of each house, in the same order.

    Returns:
        dict[str, Any]: 'num_nodes', 'coordinates' and the Euclidean 'distance_matrix',
            rounded to 2 decimals like the generator's.
    """
    to_map = _map_projection(latitudes, longitudes)
    coordinates = [list(MAP_CENTER)] + [to_map(lat, lon) for lat, lon in zip(latitudes, longitudes)]
    distance_matrix = [[0.0 if i == j else round(math.hypot(a[0] - b[0], a[1] - b[1]), 2)
                        for j, b in enumerate(coordinates)] for i, a in enumerate(coordinates)]
    return {'num_nodes': len(coordinates), 'coordinates': coordinates, 'distance_matrix': distance_matrix}


def _map_projection(latitudes: list[float], longitudes: list[float]) -> Callable[[float, float], list[float]]:
    """
    Equirectangular projection onto the generator's map, centered on the houses.

    Args:
        latitudes (list[float]): Latitude of each house.
        longitudes (list[float]): Longitude of each house, in the same order.

    Returns:
        Callable[[float, float], list[float]]: Maps a latitude and a longitude to (x, y): the
            centroid of the houses at MAP_CENTER, MAP_UNITS_PER_KM units per kilometer, east
            along x and north along y.
    """
    origin_lat = sum(latitudes) / len(latitudes)
    origin_lon = sum(longitudes) / len(longitudes)
    km_per_degree_lon = KM_PER_DEGREE_LON * math.cos(math.radians(origin_lat))

    def to_map(lat: float, lon: float) -> list[float]:
        return [MAP_CENTER[0] + (lon - origin_lon) * km_per_degree_lon * MAP_UNITS_PER_KM,
                MAP_CENTER[1] + (lat - origin_lat) * KM_PER_DEGREE_LAT * MAP_UNITS_PER_KM]

    return to_map


def _convex_hull(points: list[list[float]]) -> list[list[float]]:
    """
    Convex hull of (x, y) points, counter-clockwise, without collinear vertices: the
    polygon of the region they cover.
    """
    unique = sorted({(float(x), float(y)) for x, y in points})
    if len(unique) <= 2:
        return [list(point) for point in unique]

    def cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

    lower: list[tuple[float, float]] = []
    upper: list[tuple[float, float]] = []
    for chain, ordered in ((lower, unique), (upper, reversed(unique))):
        for point in ordered:
            while len(chain) >= 2 and cross(chain[-2], chain[-1], point) <= 0:
                chain.pop()
            chain.append(point)
    return [list(point) for point in lower[:-1] + upper[:-1]]


def _listing_record(node: int, row: Any) -> dict[str, Any]:
    """The catalog row behind a node, for logs and results."""
    return {
        "node": node,
        "id": str(row.id),
        "address": row.address,
        "district": row.district,
        "city": row.city,
        "lat": float(row.lat),
        "lon": float(row.lon),
        "area": float(row.area),
        "bedrooms": int(row.bedrooms),
        "garage": int(row.garage),
        "type": row.type,
        "rent": float(row.rent),
        "total": float(row.total),
    }
