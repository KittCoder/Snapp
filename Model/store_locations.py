"""Static verified catalog coordinates; no runtime geocoding.
C-Town: NYC Planning GeoSearch address points, precomputed 2026-10-25.
Food Bazaar: coordinates captured with each verified retailer-location record.
Morton Williams is an unlocated catalog, not a verified physical branch.
"""
STORE_COORDINATES = {
    "ctown:PS41_311": [
        40.714256,
        -73.944018
    ],
    "ctown:PU41_023": [
        40.694622,
        -73.847377
    ],
    "ctown:PU41_071": [
        40.605218,
        -74.082827
    ],
    "ctown:PU41_115": [
        40.672383,
        -73.894319
    ],
    "ctown:PU41_199": [
        40.666699,
        -73.931627
    ],
    "ctown:PU41_369": [
        40.835063,
        -73.93939
    ],
    "ctown:U41_022": [
        40.849222,
        -73.787635
    ],
    "ctown:U41_131": [
        40.771311,
        -73.925143
    ],
    "ctown:U41_186": [
        40.690893,
        -73.959314
    ],
    "ctown:U41_205": [
        40.695078,
        -73.790524
    ],
    "ctown:U41_207": [
        40.663332,
        -73.921537
    ],
    "ctown:U41_496": [
        40.873893,
        -73.884053
    ]
}

# Coordinates captured with each verified Food Bazaar physical catalog.
import json as _json
from pathlib import Path as _Path
_food_bazaar_coordinates = _Path(__file__).with_name('food_bazaar_store_coordinates.json')
if _food_bazaar_coordinates.exists():
    STORE_COORDINATES.update(_json.loads(_food_bazaar_coordinates.read_text()))
