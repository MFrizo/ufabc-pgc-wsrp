"""
Module: listings
Description: Builds a WSRP instance from a real rental catalog, as an alternative to the
             synthetic generator. Listings are São Paulo rentals with a latitude and a
             longitude. Those coordinates are laid on the same 100x100 map the generator
             uses, keeping distances proportional, and the visit length grows with the
             usable area. Scheduled times, broker assignments and homes still come from
             the hidden schedule, which keeps the instance feasible.
"""

import math
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.core.data_generator import _complete_instance, generate_wsrp_instance
from src.models import INSTANCE_SETTINGS

# Catalog shipped with the repo: cleaned São Paulo rental listings.
REAL_CATALOG = Path(__file__).resolve().parents[2] / "data" / "real.csv"

DATASETS = ("synthetic", "real")

# Floor area, in m², that maps to the longest visit. Larger homes stay at that length.
AREA_REFERENCE = 240

# Usable area accepted as a real home. The catalog contains placeholders and outliers.
MIN_AREA = 10
MAX_AREA = 1000

# City the routes are planned in. A national sample would join visits no broker can reach.
DEFAULT_CITY = "São Paulo"

# Percentiles 1 and 99 of the São Paulo catalog. The box is mapped onto the 100x100
# grid isotropically, so a kilometer keeps the same length on both axes.
LAT_SOUTH = -23.662344
LAT_NORTH = -23.471914
LON_WEST = -46.755281
LON_EAST = -46.508928
LAT_REFERENCE = -23.55
KM_PER_DEGREE_LAT = 110.574
KM_PER_DEGREE_LON = 111.320 * math.cos(math.radians(LAT_REFERENCE))

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
                  catalog_path: Optional[str] = None) -> dict[str, Any]:
    """
    Builds the instance a model runs on, either from the generator or from the real catalog.

    Args:
        dataset (str): "synthetic" or "real".
        model_version (str): Key of src.models.BUILDERS. Selects that model's generator settings.
        num_properties (int): Number of properties in the instance.
        random_seed (int): Seed of the sample and of the hidden schedule.
        catalog_path (Optional[str]): Real-listings CSV. Defaults to the São Paulo extract in the repo.
            The original semicolon export is accepted too.

    Returns:
        dict[str, Any]: The instance payload. A real instance also carries 'listings'.

    Raises:
        ValueError: If dataset is unknown or the catalog cannot supply the sample.
    """
    if dataset not in DATASETS:
        raise ValueError(f"dataset must be one of: {', '.join(DATASETS)}.")

    settings = INSTANCE_SETTINGS[model_version]
    if dataset == "synthetic":
        return generate_wsrp_instance(num_properties=num_properties, random_seed=random_seed, **settings)

    path = catalog_path or REAL_CATALOG
    return instance_from_dataset(str(path), num_properties=num_properties, random_seed=random_seed, **settings)


def instance_from_dataset(path: str, num_properties: int = 5, random_seed: int = 42, num_brokers: int = 1,
                          travel_time: int = 30, service_time: int = 60, horizon: int = 600,
                          fixed_ratio: float = 0.2, window_width: tuple[int, int] = (120, 360),
                          assigned_ratio: float = 0.4, service_time_variation: int = 0,
                          speed_profile: Optional[list[tuple[int, float]]] = None,
                          working_hours: tuple[int, int] = (0, 540),
                          start_at_homes: bool = False, city: str = DEFAULT_CITY) -> dict[str, Any]:
    """
    Samples listings from the real catalog and builds the instance every model reads.

    Args:
        path (str): Semicolon-separated CSV, either the original export or the cleaned extract.
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

    Returns:
        dict[str, Any]: The instance payload of generate_wsrp_instance, plus 'listings'.

    Raises:
        ValueError: If the file is missing columns or is smaller than the requested sample.
    """
    catalog = load_real_catalog(path, city=city)
    if num_properties < 1:
        raise ValueError("num_properties must be at least 1.")
    if num_properties > len(catalog):
        raise ValueError(f"The catalog has {len(catalog)} listings in {city}, fewer than {num_properties}.")

    rng = np.random.default_rng(random_seed)
    chosen = catalog.iloc[rng.choice(len(catalog), size=num_properties, replace=False)].reset_index(drop=True)

    property_coordinates = [_project(row.lat, row.lon) for row in chosen.itertuples(index=False)]
    agency = [round(sum(point[0] for point in property_coordinates) / num_properties, 2),
              round(sum(point[1] for point in property_coordinates) / num_properties, 2)]
    coordinates = [agency, *property_coordinates]

    data_payload = {
        "num_nodes": num_properties + 1,
        "coordinates": coordinates,
        "distance_matrix": _distance_matrix(coordinates),
        "service_times": [0] + [_service_minutes(int(row.area), service_time, service_time_variation)
                                for row in chosen.itertuples(index=False)],
        "listings": [_listing_record(node, row) for node, row in enumerate(chosen.itertuples(index=False), start=1)],
    }
    return _complete_instance(data_payload, random_seed=random_seed, num_brokers=num_brokers,
                              travel_time=travel_time, service_time=service_time, horizon=horizon,
                              fixed_ratio=fixed_ratio, window_width=window_width, assigned_ratio=assigned_ratio,
                              speed_profile=speed_profile, working_hours=working_hours,
                              start_at_homes=start_at_homes)


def load_real_catalog(path: str, city: str = DEFAULT_CITY) -> pd.DataFrame:
    """
    Reads the real catalog, or the original semicolon export, and keeps the listings a route can visit.

    Args:
        path (str): CSV path.
        city (str): City to keep.

    Returns:
        pd.DataFrame: One row per distinct address, in file order, with CATALOG_COLUMNS.

    Raises:
        ValueError: If a required column is missing or no listing remains.
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

    usable = (
        catalog["city"].astype(str).str.strip().eq(city)
        & catalog["lat"].between(-24.0, -23.2)
        & catalog["lon"].between(-47.2, -46.2)
        & catalog["area"].between(MIN_AREA, MAX_AREA)
        & catalog["rent"].gt(0)
        & ~_missing_label(catalog["address"])
        & ~_missing_label(catalog["district"])
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
    if catalog.empty:
        raise ValueError(f"Listing file has no usable rows in {city}: {path}")
    return catalog.reset_index(drop=True)


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


def _project(lat: float, lon: float) -> list[float]:
    """
    (x, y) on the 100x100 map. A kilometer has the same length on both axes, and the
    percentile box of the city fills the grid.
    """
    span_km = max((LAT_NORTH - LAT_SOUTH) * KM_PER_DEGREE_LAT, (LON_EAST - LON_WEST) * KM_PER_DEGREE_LON)
    x = (lon - LON_WEST) * KM_PER_DEGREE_LON / span_km * 100.0
    y = (lat - LAT_SOUTH) * KM_PER_DEGREE_LAT / span_km * 100.0
    return [round(x, 2), round(y, 2)]


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
    """True where the catalog stored a placeholder instead of an address, a district or a type."""
    return values.astype(str).str.strip().str.lower().isin(MISSING_LABELS)
