"""
Module: real_catalog
Description: Converts the raw real rental catalog into the cleaned one. The catalog is a
             snapshot of a Brazilian real estate company, published at
             https://www.kaggle.com/datasets/maverickjpa/brazilian-real-estate-to-rent
             data/raw_real.csv.gz is that export as published. data/real.csv is its
             cleaned version: every listing has a city, a neighborhood and coordinates
             inside its own city, and appears once.
             Rebuild data/real.csv with: python -m src.utils.real_catalog
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Snapshot of a Brazilian real estate company
REAL_CATALOG_SOURCE = "https://www.kaggle.com/datasets/maverickjpa/brazilian-real-estate-to-rent"

# That snapshot as published, and its cleaned version, both shipped with the repo.
RAW_REAL_CATALOG = Path(__file__).resolve().parents[2] / "data" / "raw_real.csv.gz"
REAL_CATALOG = Path(__file__).resolve().parents[2] / "data" / "real.csv"

# Usable area accepted as a real home. The catalog contains placeholders and outliers.
MIN_AREA = 10
MAX_AREA = 1000

# Brazil, loose enough to keep every city in the snapshot and drop broken coordinates.
BRAZIL_LAT = (-34.0, 6.0)
BRAZIL_LON = (-74.0, -32.0)

# Equirectangular kilometers. Longitude shrinks with the latitude.
KM_PER_DEGREE_LAT = 110.574
KM_PER_DEGREE_LON = 111.320

# Farthest a listing may sit from the median coordinate of its own city. The snapshot's
# real listings stay within 40 km (Guaratiba, in Rio); the next ones are 52 km to
# 1,164 km away, carrying the city's name with another place's coordinates.
MAX_KM_FROM_CITY = 50.0

# Labels the catalog uses where a value is missing.
MISSING_LABELS = {"", "normal", "nan", "none", "<na>"}

# Headers of the original semicolon export, mapped to the columns of the cleaned catalog.
EXPORT_RENAME = {
    "listing.id": "id",
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

CATALOG_COLUMNS = ("id", "address", "district", "city", "lat", "lon", "area", "bedrooms", "garage", "type", "rent",
                   "total")


def clean_real_catalog(path: str) -> pd.DataFrame:
    """
    Cleans the real catalog of every city. REAL_CATALOG is this function applied to
    RAW_REAL_CATALOG; running it again on REAL_CATALOG keeps every row.

    Drops the listings without a city or a neighborhood, including the "normal"
    placeholder, the ones without coordinates, outside Brazil or more than
    MAX_KM_FROM_CITY from the median coordinate of their city, and the ones a visit
    cannot use: no address or type, an implausible area, no rent or no geocode. A
    listing published more than once is kept once, by its id. Apartments that share
    a building, and therefore an address, stay separate listings.

    Args:
        path (str): Semicolon-separated CSV, either the original export or the cleaned catalog.

    Returns:
        pd.DataFrame: One row per listing id, in file order, with CATALOG_COLUMNS.

    Raises:
        ValueError: If a required column is missing.
    """
    catalog = pd.read_csv(path, sep=";", low_memory=False)
    # The export's own "type" column is the publication tier (premium), not the property kind.
    if "listing.unitTypes" in catalog.columns and "type" in catalog.columns:
        catalog = catalog.drop(columns=["type"])
    catalog = catalog.rename(
        columns={source: target for source, target in EXPORT_RENAME.items() if source in catalog.columns})

    missing = [column for column in CATALOG_COLUMNS if column not in catalog.columns]
    if missing:
        raise ValueError(f"Listing file is missing columns: {', '.join(missing)}.")

    catalog = catalog.loc[:, [*CATALOG_COLUMNS, *(["precision"] if "precision" in catalog.columns else [])]].copy()
    # The export repeats an ad once per property-type search that found it. Apartments of
    # one building share the street and often the coordinates, so only the id tells two
    # listings apart.
    catalog = catalog.drop_duplicates(subset=["id"], keep="first")
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
    catalog = catalog.loc[km_from_city_median(catalog).le(MAX_KM_FROM_CITY)]

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


def km_from_city_median(catalog: pd.DataFrame) -> pd.Series:
    """Distance, in kilometers, from each listing to the median coordinate of its city."""
    median = catalog.groupby("city")[["lat", "lon"]].transform("median")
    km_per_degree_lon = KM_PER_DEGREE_LON * np.cos(np.radians(median["lat"]))
    return np.hypot((catalog["lat"] - median["lat"]) * KM_PER_DEGREE_LAT,
                    (catalog["lon"] - median["lon"]) * km_per_degree_lon)


def _first_number(values: pd.Series) -> pd.Series:
    """First number in each cell, so a value stored as text or as a one-item list still counts."""
    return pd.to_numeric(values.astype(str).str.extract(r"(-?\d+(?:\.\d+)?)", expand=False), errors="coerce")


def _missing_label(values: pd.Series) -> pd.Series:
    """True where the catalog stored a placeholder instead of a city, an address, a district or a type."""
    return values.astype(str).str.strip().str.lower().isin(MISSING_LABELS)


if __name__ == "__main__":
    cleaned = build_real_catalog()
    print(f"{len(cleaned)} listings in {cleaned['city'].nunique()} cities written to {REAL_CATALOG}")
