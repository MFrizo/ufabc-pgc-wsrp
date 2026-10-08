"""
Module: listings
Description: Builds a WSRP instance from a real rental catalog, as an alternative to the
             synthetic generator. The catalog is a snapshot of a Brazilian real estate
             company, published at
             https://www.kaggle.com/datasets/maverickjpa/brazilian-real-estate-to-rent
             data/raw_real.csv.gz is that export as published. data/real.csv is its
             cleaned version, the one the instances read: every listing has a city,
             a neighborhood and coordinates inside its own city. Each call keeps one
             city and one neighborhood: the national file is too large for the solver,
             and a broker does not travel from one city to another. The graph of the houses
             is built from listing.address.point.lat and listing.address.point.lon:
             each edge is the straight-line separation of those two coordinates, on
             the same scale the generator uses. The visit length grows with the
             usable area. Each broker's home is a random latitude and longitude inside
             the polygon of the city. Scheduled times and broker assignments
             still come from the hidden schedule, which keeps the instance feasible.
"""

import math
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.core.data_generator import HOMES_STREAM, _complete_instance, generate_wsrp_instance
from src.models import INSTANCE_SETTINGS
from src.utils.logger import project_logger

# Snapshot of a Brazilian real estate company:
# https://www.kaggle.com/datasets/maverickjpa/brazilian-real-estate-to-rent
REAL_CATALOG_SOURCE = "https://www.kaggle.com/datasets/maverickjpa/brazilian-real-estate-to-rent"

# That snapshot as published, and its cleaned version, both shipped with the repo.
RAW_REAL_CATALOG = Path(__file__).resolve().parents[2] / "data" / "raw_real.csv.gz"
REAL_CATALOG = Path(__file__).resolve().parents[2] / "data" / "real.csv"

DATASETS = ("synthetic", "real")

# Floor area, in m², that maps to the longest visit. Larger homes stay at that length.
AREA_REFERENCE = 240

# Usable area accepted as a real home. The catalog contains placeholders and outliers.
MIN_AREA = 10
MAX_AREA = 1000

# City the routes are planned in when the caller does not need another one.
# A national sample would join visits no broker can reach.
DEFAULT_CITY = "São Paulo"

# Brazil, loose enough to keep every city in the snapshot and drop broken coordinates.
BRAZIL_LAT = (-34.0, 6.0)
BRAZIL_LON = (-74.0, -32.0)

# Equirectangular kilometers. Longitude shrinks with the latitude of the sample.
KM_PER_DEGREE_LAT = 110.574
KM_PER_DEGREE_LON = 111.320

# The generator draws the city on a 100x100 map, about 25 km across, so one kilometer
# is 4 units and a speed of 2 units per minute is about 30 km/h. The houses keep that
# scale; their positions come from the listing coordinates, not from that box.
MAP_UNITS_PER_KM = 4.0

# Farthest a listing may sit from the median coordinate of its own city. The snapshot's
# real listings stay within 40 km (Guaratiba, in Rio); the next ones are 52 km to
# 1,164 km away, carrying the city's name with another place's coordinates.
MAX_KM_FROM_CITY = 50.0

# Labels the catalog uses where a value is missing.
MISSING_LABELS = {"", "normal", "nan", "none", "<na>"}

# Headers of the original semicolon export, mapped to the columns the instance reads.
EXPORT_RENAME = {
    "listing.address.street": "address",
    "listing.address.neighborhood": "district",
    "listing.address.city": "city",
    "listing.address.point.lat": "lat",
    "listing.address.point.lon": "lon",
    "listing.usableAreas": "area",
    "listing.bedrooms": "bedrooms",
    "listing.parkingSpaces": "garage",
    "listing.unitTypes": "type",
    "listing.pricingInfo.rentalPrice": "rent",
    "listing.pricingInfo.rentalTotalPrice": "total",
    "listing.address.precision": "precision",
}

CATALOG_COLUMNS = ("address", "district", "city", "lat", "lon", "area", "bedrooms", "garage", "type", "rent", "total")


def load_instance(dataset: str, model_version: str, num_properties: int = 5, random_seed: int = 42,
                  catalog_path: Optional[str] = None, city: Optional[str] = None,
                  neighborhood: Optional[str] = None) -> dict[str, Any]:
    """
    Builds the instance a model runs on, either from the generator or from the real catalog.

    Args:
        dataset (str): "synthetic" or "real".
        model_version (str): Key of src.models.BUILDERS. Selects that model's generator settings.
        num_properties (int): Number of properties in the instance.
        random_seed (int): Seed of the sample and of the hidden schedule.
        catalog_path (Optional[str]): Real-listings CSV. Defaults to REAL_CATALOG, the cleaned
            version of REAL_CATALOG_SOURCE. RAW_REAL_CATALOG is accepted too, and cleaned the same way.
        city (Optional[str]): City of a real instance. Required when dataset is "real".
        neighborhood (Optional[str]): Neighborhood of a real instance. Required when dataset is
            "real". The sample is drawn only from this neighborhood of this city.

    Returns:
        dict[str, Any]: The instance payload. A real instance also carries 'listings'.

    Raises:
        ValueError: If dataset is unknown, a real call omits the city or the neighborhood,
            or the catalog cannot supply the sample.
    """
    if dataset not in DATASETS:
        raise ValueError(f"dataset must be one of: {', '.join(DATASETS)}.")

    settings = INSTANCE_SETTINGS[model_version]
    if dataset == "synthetic":
        return generate_wsrp_instance(num_properties=num_properties, random_seed=random_seed, **settings)

    if not city or not str(city).strip() or not neighborhood or not str(neighborhood).strip():
        raise ValueError(
            "A real instance needs a city and a neighborhood. "
            "The full catalog is too large for the solver, and a broker does not travel between cities."
        )

    path = catalog_path or REAL_CATALOG
    project_logger.info(
        "Real listings are a snapshot of a Brazilian real estate company: "
        f"{REAL_CATALOG_SOURCE}"
    )
    return instance_from_dataset(str(path), num_properties=num_properties, random_seed=random_seed,
                                 city=city.strip(), neighborhood=neighborhood.strip(), **settings)


def instance_from_dataset(path: str, num_properties: int = 5, random_seed: int = 42, num_brokers: int = 1,
                          travel_time: int = 30, service_time: int = 60, horizon: int = 600,
                          fixed_ratio: float = 0.2, window_width: tuple[int, int] = (120, 360),
                          assigned_ratio: float = 0.4, service_time_variation: int = 0,
                          speed_profile: Optional[list[tuple[int, float]]] = None,
                          working_hours: tuple[int, int] = (0, 540),
                          start_at_homes: bool = False, city: str = DEFAULT_CITY,
                          neighborhood: Optional[str] = None) -> dict[str, Any]:
    """
    Samples listings from the real catalog and builds the instance every model reads.

    Args:
        path (str): Semicolon-separated CSV, either the original export or the cleaned catalog.
        num_properties (int): How many listings become visits.
        random_seed (int): Seed for the sample and for the hidden schedule.
        num_brokers (int): Number of brokers |K|.
        travel_time (int): Constant travel time T, used when there is no speed profile.
        service_time (int): Visit duration S, in minutes, used as-is when there is no variation
            and as the middle of the range otherwise.
        horizon (int): Target length of the working day, in minutes.
        fixed_ratio (float): Share of the properties with a fixed start time.
        window_width (tuple[int, int]): Min and max width of a flexible time window, in minutes.
        assigned_ratio (float): Share of the properties whose visit already has a broker.
        service_time_variation (int): Half-width of the visit-length range. A home of
            AREA_REFERENCE m² lasts S + variation minutes; a home of 0 m² lasts S - variation.
        speed_profile (Optional[list[tuple[int, float]]]): Periods of the day as (start minute,
            speed in distance units per minute). With None, every trip takes T.
        working_hours (tuple[int, int]): Start and regular end of every broker's working day.
        start_at_homes (bool): Whether each broker of the hidden schedule leaves his own home.
        city (str): City the sample is drawn from.
        neighborhood (Optional[str]): Neighborhood the sample is drawn from. Required: the
            solver receives only this neighborhood of this city. Broker homes are drawn
            anywhere inside the city.

    Returns:
        dict[str, Any]: The instance payload of generate_wsrp_instance, plus 'listings'.

    Raises:
        ValueError: If the neighborhood is missing, the file is missing columns, or the
            neighborhood has fewer listings than the requested sample.
    """
    if not neighborhood or not str(neighborhood).strip():
        raise ValueError(
            "A real instance needs a neighborhood. "
            "The full catalog is too large for the solver, and a broker does not travel between cities."
        )

    neighborhood = neighborhood.strip()
    city_catalog = load_real_catalog(path, city=city)
    catalog = city_catalog.loc[city_catalog["district"].eq(neighborhood)].reset_index(drop=True)
    if catalog.empty:
        raise ValueError(f"No usable listings in {neighborhood}, {city.strip()}: {path}")
    if num_properties < 1:
        raise ValueError("num_properties must be at least 1.")
    if num_properties > len(catalog):
        raise ValueError(
            f"{neighborhood}, {city} has {len(catalog)} listings, fewer than {num_properties}."
        )

    project_logger.info(
        f"Sampling {num_properties} of {len(catalog)} listings in {neighborhood}, {city}."
    )

    rng = np.random.default_rng(random_seed)
    chosen = catalog.iloc[rng.choice(len(catalog), size=num_properties, replace=False)].reset_index(drop=True)
    rows = list(chosen.itertuples(index=False))

    # listing.address.point.lat / listing.address.point.lon, renamed to lat / lon.
    # The agency sits at the centroid of the sampled houses. Broker homes are other
    # points of the same projection, drawn inside the city's polygon.
    house_lat = [row.lat for row in rows]
    house_lon = [row.lon for row in rows]
    origin_lat, origin_lon, km_per_degree_lon = _map_frame(house_lat, house_lon)
    coordinates = _house_graph(house_lat, house_lon, origin_lat, origin_lon, km_per_degree_lon)
    project_logger.info(f"Placing {num_brokers} broker homes inside the polygon of {city}.")
    homes = _broker_homes(random_seed, city_catalog["lat"].tolist(), city_catalog["lon"].tolist(), num_brokers,
                          origin_lat, origin_lon, km_per_degree_lon)

    data_payload = {
        "num_nodes": num_properties + 1,
        "coordinates": coordinates,
        "distance_matrix": _distance_matrix(coordinates),
        "service_times": [0] + [_service_minutes(int(row.area), service_time, service_time_variation) for row in rows],
        "listings": [_listing_record(node, row) for node, row in enumerate(rows, start=1)],
    }
    return _complete_instance(data_payload, random_seed=random_seed, num_brokers=num_brokers,
                              travel_time=travel_time, service_time=service_time, horizon=horizon,
                              fixed_ratio=fixed_ratio, window_width=window_width, assigned_ratio=assigned_ratio,
                              speed_profile=speed_profile, working_hours=working_hours,
                              start_at_homes=start_at_homes, home_coordinates=homes)


def load_real_catalog(path: str, city: str = DEFAULT_CITY, neighborhood: Optional[str] = None) -> pd.DataFrame:
    """
    Reads the real catalog, or the original semicolon export, and keeps the listings a route can visit.

    Args:
        path (str): CSV path.
        city (str): City to keep.
        neighborhood (Optional[str]): Neighborhood to keep inside that city. With None, every
            neighborhood of the city is returned.

    Returns:
        pd.DataFrame: One row per distinct address, in file order, with CATALOG_COLUMNS.

    Raises:
        ValueError: If a required column is missing or no listing remains.
    """
    catalog = clean_real_catalog(path)
    catalog = catalog.loc[catalog["city"].eq(city.strip())]
    if neighborhood is not None:
        catalog = catalog.loc[catalog["district"].eq(neighborhood.strip())].reset_index(drop=True)
        if catalog.empty:
            raise ValueError(f"No usable listings in {neighborhood.strip()}, {city.strip()}: {path}")
    if catalog.empty:
        raise ValueError(f"Listing file has no usable rows in {city.strip()}: {path}")
    return catalog.reset_index(drop=True)


def clean_real_catalog(path: str) -> pd.DataFrame:
    """
    Cleans the real catalog of every city. REAL_CATALOG is this function applied to
    RAW_REAL_CATALOG; running it again on REAL_CATALOG keeps every row.

    Drops the listings without a city or a neighborhood, including the "normal"
    placeholder, the ones without coordinates, outside Brazil or more than
    MAX_KM_FROM_CITY from the median coordinate of their city, and the ones a visit
    cannot use: no address or type, an implausible area, no rent, no geocode, or a
    second copy of the same address.

    Args:
        path (str): Semicolon-separated CSV, either the original export or the cleaned catalog.

    Returns:
        pd.DataFrame: One row per distinct address, in file order, with CATALOG_COLUMNS.

    Raises:
        ValueError: If a required column is missing.
    """
    catalog = pd.read_csv(path, sep=";", low_memory=False)
    # The export's own "type" column is the publication tier (premium), not the property kind.
    if "listing.unitTypes" in catalog.columns and "type" in catalog.columns:
        catalog = catalog.drop(columns=["type"])
    catalog = catalog.rename(columns={source: target for source, target in EXPORT_RENAME.items() if source in catalog.columns})

    missing = [column for column in CATALOG_COLUMNS if column not in catalog.columns]
    if missing:
        raise ValueError(f"Listing file is missing columns: {', '.join(missing)}.")

    catalog = catalog.loc[:, [*CATALOG_COLUMNS, *(["precision"] if "precision" in catalog.columns else [])]].copy()
    catalog["lat"] = pd.to_numeric(catalog["lat"], errors="coerce")
    catalog["lon"] = pd.to_numeric(catalog["lon"], errors="coerce")
    catalog["area"] = _first_number(catalog["area"])
    catalog["bedrooms"] = _first_number(catalog["bedrooms"]).fillna(0)
    catalog["garage"] = _first_number(catalog["garage"]).fillna(0)
    catalog["rent"] = _first_number(catalog["rent"])
    catalog["total"] = _first_number(catalog["total"]).fillna(catalog["rent"])

    placed = (
        ~_missing_label(catalog["city"])
        & ~_missing_label(catalog["district"])
        & catalog["lat"].between(*BRAZIL_LAT)
        & catalog["lon"].between(*BRAZIL_LON)
    )
    catalog = catalog.loc[placed].copy()
    catalog["city"] = catalog["city"].astype(str).str.strip()
    catalog = catalog.loc[_km_from_city_median(catalog).le(MAX_KM_FROM_CITY)]

    usable = (
        catalog["area"].between(MIN_AREA, MAX_AREA)
        & catalog["rent"].gt(0)
        & ~_missing_label(catalog["address"])
        & ~_missing_label(catalog["type"])
    )
    if "precision" in catalog.columns:
        usable &= catalog["precision"].astype(str).ne("Precision_NONE")

    catalog = catalog.loc[usable, list(CATALOG_COLUMNS)].copy()
    catalog["address"] = catalog["address"].astype(str).str.strip()
    catalog["district"] = catalog["district"].astype(str).str.strip()
    catalog["type"] = catalog["type"].astype(str).str.strip()
    catalog["_lat_key"] = catalog["lat"].round(5)
    catalog["_lon_key"] = catalog["lon"].round(5)
    catalog = catalog.drop_duplicates(subset=["address", "district", "_lat_key", "_lon_key"], keep="first")
    catalog = catalog.drop(columns=["_lat_key", "_lon_key"])
    return catalog.reset_index(drop=True)


def build_real_catalog(raw_path: str = str(RAW_REAL_CATALOG), output_path: str = str(REAL_CATALOG)) -> pd.DataFrame:
    """
    Writes REAL_CATALOG, the cleaned version of RAW_REAL_CATALOG, as a semicolon CSV.

    Args:
        raw_path (str): The original export.
        output_path (str): Where the cleaned catalog is written.

    Returns:
        pd.DataFrame: The rows written.
    """
    catalog = clean_real_catalog(raw_path)
    catalog.to_csv(output_path, sep=";", index=False)
    return catalog


def _km_from_city_median(catalog: pd.DataFrame) -> pd.Series:
    """Distance, in kilometers, from each listing to the median coordinate of its city."""
    median = catalog.groupby("city")[["lat", "lon"]].transform("median")
    km_per_degree_lon = KM_PER_DEGREE_LON * np.cos(np.radians(median["lat"]))
    return np.hypot((catalog["lat"] - median["lat"]) * KM_PER_DEGREE_LAT,
                    (catalog["lon"] - median["lon"]) * km_per_degree_lon)


def _listing_record(node: int, row: Any) -> dict[str, Any]:
    """One sampled listing, tagged with the graph node of its visit."""
    return {
        "node": node,
        "address": row.address,
        "district": row.district,
        "city": row.city,
        "lat": float(row.lat),
        "lon": float(row.lon),
        "area": int(round(row.area)),
        "bedrooms": int(round(row.bedrooms)),
        "garage": int(round(row.garage)),
        "type": row.type,
        "rent": int(round(row.rent)),
        "total": int(round(row.total)),
    }


def _service_minutes(area: int, service_time: int, service_time_variation: int) -> int:
    """
    Visit length, in minutes, growing with the usable area and clipped to
    [S - variation, S + variation].
    """
    low = service_time - service_time_variation
    high = service_time + service_time_variation
    if high == low:
        return service_time
    capped = min(max(area, 0), AREA_REFERENCE)
    return int(round(low + capped / AREA_REFERENCE * (high - low)))


def _map_frame(latitudes: list[float], longitudes: list[float]) -> tuple[float, float, float]:
    """
    Origin and longitude scale of the equirectangular projection.

    The origin is the centroid of the given coordinates. Longitude is scaled at that
    latitude, so a kilometer has the same length east and north.
    """
    origin_lat = sum(latitudes) / len(latitudes)
    origin_lon = sum(longitudes) / len(longitudes)
    km_per_degree_lon = KM_PER_DEGREE_LON * math.cos(math.radians(origin_lat))
    return origin_lat, origin_lon, km_per_degree_lon


def _to_map(lat: float, lon: float, origin_lat: float, origin_lon: float,
            km_per_degree_lon: float) -> list[float]:
    """(x, y) of one coordinate, in map units, rounded to 2 decimal places."""
    east_km = (lon - origin_lon) * km_per_degree_lon
    north_km = (lat - origin_lat) * KM_PER_DEGREE_LAT
    return [round(50.0 + east_km * MAP_UNITS_PER_KM, 2), round(50.0 + north_km * MAP_UNITS_PER_KM, 2)]


def _house_graph(latitudes: list[float], longitudes: list[float], origin_lat: float, origin_lon: float,
                 km_per_degree_lon: float) -> list[list[float]]:
    """
    (x, y) of the agency and of every house.

    Each house is placed from listing.address.point.lat and listing.address.point.lon.
    The centroid of those houses is the agency.

    Args:
        latitudes (list[float]): listing.address.point.lat of each house, in degrees.
        longitudes (list[float]): listing.address.point.lon of each house, in degrees.
        origin_lat (float): Latitude the projection measures north from.
        origin_lon (float): Longitude the projection measures east from.
        km_per_degree_lon (float): Kilometers per degree of longitude at origin_lat.

    Returns:
        list[list[float]]: Index 0 is the agency. The following points are the houses,
            in the same order.
    """
    houses = [_to_map(lat, lon, origin_lat, origin_lon, km_per_degree_lon)
              for lat, lon in zip(latitudes, longitudes)]
    agency = [round(sum(point[0] for point in houses) / len(houses), 2),
              round(sum(point[1] for point in houses) / len(houses), 2)]
    return [agency, *houses]


def _broker_homes(random_seed: int, latitudes: list[float], longitudes: list[float], num_brokers: int,
                  origin_lat: float, origin_lon: float, km_per_degree_lon: float) -> list[list[float]]:
    """
    (x, y) of each broker's home, drawn inside the city polygon.

    The polygon is the convex hull of listing.address.point.lat and
    listing.address.point.lon for the city's listings. Each home is a uniform
    point of that polygon, then placed with the same projection as the houses.

    Args:
        random_seed (int): Seed of the draw.
        latitudes (list[float]): listing.address.point.lat of every listing in the city.
        longitudes (list[float]): listing.address.point.lon of every listing in the city.
        num_brokers (int): How many homes to place.
        origin_lat (float): Latitude the projection measures north from.
        origin_lon (float): Longitude the projection measures east from.
        km_per_degree_lon (float): Kilometers per degree of longitude at origin_lat.

    Returns:
        list[list[float]]: One (x, y) per broker, in map units.
    """
    rng = np.random.default_rng([random_seed, HOMES_STREAM])
    hull = _convex_hull(list(zip(longitudes, latitudes)))
    projected_hull = [_to_map(lat, lon, origin_lat, origin_lon, km_per_degree_lon) for lon, lat in hull]
    homes = []
    for _ in range(num_brokers):
        for _attempt in range(100):
            lon, lat = _random_point_in_hull(rng, hull)
            home = _to_map(lat, lon, origin_lat, origin_lon, km_per_degree_lon)
            # Rounding can push a point that sat on the boundary just outside the projected hull.
            if len(projected_hull) < 3 or _inside_convex(home, projected_hull):
                homes.append(home)
                break
        else:
            centroid_lon = sum(point[0] for point in hull) / len(hull)
            centroid_lat = sum(point[1] for point in hull) / len(hull)
            homes.append(_to_map(centroid_lat, centroid_lon, origin_lat, origin_lon, km_per_degree_lon))
    return homes


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """
    Convex hull of (x, y) points, counter-clockwise, without the repeated closing vertex.

    Collinear points on an edge are dropped, so the hull is the polygon of the region.
    """
    unique = sorted(set(points))
    if len(unique) <= 2:
        return unique

    def cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _random_point_in_hull(rng: np.random.Generator, hull: list[tuple[float, float]]) -> tuple[float, float]:
    """A point distributed uniformly inside a convex hull, including its boundary."""
    if len(hull) == 1:
        return hull[0]
    if len(hull) == 2:
        weight = float(rng.random())
        return (hull[0][0] + weight * (hull[1][0] - hull[0][0]),
                hull[0][1] + weight * (hull[1][1] - hull[0][1]))

    origin = hull[0]
    triangles = []
    areas = []
    for index in range(1, len(hull) - 1):
        left, right = hull[index], hull[index + 1]
        area = abs((left[0] - origin[0]) * (right[1] - origin[1]) - (left[1] - origin[1]) * (right[0] - origin[0]))
        if area > 0:
            triangles.append((origin, left, right))
            areas.append(area)
    chosen = int(rng.choice(len(triangles), p=np.array(areas) / sum(areas)))
    a, b, c = triangles[chosen]
    r1 = float(rng.random())
    r2 = float(rng.random())
    if r1 + r2 > 1:
        r1, r2 = 1 - r1, 1 - r2
    return (a[0] + r1 * (b[0] - a[0]) + r2 * (c[0] - a[0]),
            a[1] + r1 * (b[1] - a[1]) + r2 * (c[1] - a[1]))


def _inside_convex(point: list[float], hull: list[list[float]], tolerance: float = 0.02) -> bool:
    """
    Whether a point lies inside a counter-clockwise convex hull.

    tolerance is the slack, in the same units as the coordinates, that absorbs rounding
    a boundary point out of the polygon.
    """
    for index, start in enumerate(hull):
        end = hull[(index + 1) % len(hull)]
        edge_x = end[0] - start[0]
        edge_y = end[1] - start[1]
        length = math.hypot(edge_x, edge_y)
        if length == 0:
            continue
        signed_distance = (edge_x * (point[1] - start[1]) - edge_y * (point[0] - start[0])) / length
        if signed_distance < -tolerance:
            return False
    return True


def _distance_matrix(coordinates: list[list[float]]) -> list[list[float]]:
    """Euclidean distances rounded to 2 decimal places, with a zero diagonal."""
    num_nodes = len(coordinates)
    matrix = np.zeros((num_nodes, num_nodes))
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                matrix[i][j] = round(math.hypot(coordinates[i][0] - coordinates[j][0],
                                                 coordinates[i][1] - coordinates[j][1]), 2)
    return matrix.tolist()


def _first_number(values: pd.Series) -> pd.Series:
    """First number in each cell, so a value stored as text or as a one-item list still counts."""
    return pd.to_numeric(values.astype(str).str.extract(r"(-?\d+(?:\.\d+)?)", expand=False), errors="coerce")


def _missing_label(values: pd.Series) -> pd.Series:
    """True where the catalog stored a placeholder instead of a city, an address, a district or a type."""
    return values.astype(str).str.strip().str.lower().isin(MISSING_LABELS)


if __name__ == "__main__":
    # Rebuilds data/real.csv from data/raw_real.csv.gz: python -m src.core.listings
    cleaned = build_real_catalog()
    print(f"{len(cleaned)} listings in {cleaned['city'].nunique()} cities written to {REAL_CATALOG}")
