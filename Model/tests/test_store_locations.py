"""Additive public locations do not alter canonical catalog identity metadata."""
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from store_catalogs import StoreMetadata
from store_locations import STORE_COORDINATES

class StoreLocationsTests(unittest.TestCase):
    def test_all_verified_ctowns_have_static_nyc_coordinates(self):
        import json
        manifest = json.loads((Path(__file__).resolve().parents[1] / 'store_catalog_manifest.json').read_text())
        for row in manifest:
            metadata = StoreMetadata(**row)
            public = metadata.public()
            self.assertEqual({k:v for k,v in public.items() if k not in ('latitude','longitude')}, asdict(metadata))
            if metadata.retailer == 'ctown':
                self.assertIn(metadata.id, STORE_COORDINATES)
                self.assertTrue(40.4 < public['latitude'] < 41)
                self.assertTrue(-74.3 < public['longitude'] < -73.6)
            else:
                self.assertIsNone(public['latitude'])
                self.assertIsNone(public['longitude'])
