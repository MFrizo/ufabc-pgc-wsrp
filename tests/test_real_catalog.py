"""
Checks that data/real.csv is the cleaned version of data/raw_real.csv.gz.
"""

import unittest

import pandas as pd

from src.utils.real_catalog import (
    MAX_KM_FROM_CITY,
    RAW_REAL_CATALOG,
    REAL_CATALOG,
    clean_real_catalog,
    km_from_city_median,
)


class RealCatalogTest(unittest.TestCase):
    def test_real_catalog_is_the_cleaned_raw_export(self):
        real = pd.read_csv(REAL_CATALOG, sep=";")
        cleaned = clean_real_catalog(RAW_REAL_CATALOG)

        pd.testing.assert_frame_equal(real, cleaned, check_dtype=False)
        self.assertFalse(real[["city", "district", "lat", "lon"]].isna().any().any())
        self.assertFalse(real["district"].str.strip().str.lower().eq("normal").any())
        self.assertLessEqual(km_from_city_median(real).max(), MAX_KM_FROM_CITY)
        self.assertGreater(real["city"].nunique(), 1)

    def test_cleaning_the_real_catalog_keeps_every_row(self):
        real = pd.read_csv(REAL_CATALOG, sep=";")

        pd.testing.assert_frame_equal(clean_real_catalog(REAL_CATALOG), real, check_dtype=False)

    def test_listings_of_one_building_stay_separate(self):
        raw = pd.read_csv(RAW_REAL_CATALOG, sep=";", low_memory=False)
        real = pd.read_csv(REAL_CATALOG, sep=";")

        self.assertTrue(real["id"].is_unique)
        self.assertLessEqual(len(real), raw["listing.id"].nunique())
        same_point = real.groupby(["address", "district", "lat", "lon"])["id"].nunique()
        self.assertGreater(same_point.max(), 1)


if __name__ == "__main__":
    unittest.main()
