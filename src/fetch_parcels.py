"""Fetch a township's parcel-boundary polygons from NJOGIS, per city.

Source: NJ Office of GIS "Parcels and MOD-IV Composite of NJ" hosted feature
service. Pulls only the city's township (by MUN_NAME) as GeoJSON in WGS84
(lat/lon), paginated. Caches to output/<city>/parcels.geojson so it's fetched
once.

Each feature's properties carry normalized `block` / `lot` (leading zeros
stripped) so they join to merged.csv's Block/Lot. ~97% of sale parcels match.

Usage:
    python3 src/fetch_parcels.py livingston      # or millburn
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

from config import City, get_city

LAYER = ("https://services2.arcgis.com/XVOqAjTOJ5P6ngMu/arcgis/rest/services/"
         "Parcels_Composite_NJ_WM/FeatureServer/0/query")
PAGE = 2000


def norm(s) -> str:
    """Normalize a block/lot string to match merged.csv (strip leading zeros)."""
    s = str(s).strip()
    if "." in s:
        return s.lstrip("0")
    return s.lstrip("0") or "0"


def _fetch_page(city: City, offset: int) -> dict:
    q = urllib.parse.urlencode({
        "where": f"MUN_NAME='{city.mun_name}'",
        "outFields": "PAMS_PIN,PCLBLOCK,PCLLOT,PCLQCODE,PROP_LOC",
        "outSR": 4326,            # WGS84 lat/lon, matches the geocode cache
        "resultOffset": offset,
        "resultRecordCount": PAGE,
        "f": "geojson",
    })
    with urllib.request.urlopen(f"{LAYER}?{q}", timeout=120) as r:
        return json.load(r)


def fetch_parcels(city: City) -> dict:
    features = []
    offset = 0
    while True:
        page = _fetch_page(city, offset)
        fs = page.get("features", [])
        features.extend(fs)
        print(f"  [{city.name}] fetched {len(features)} parcels...")
        if len(fs) < PAGE:
            break
        offset += PAGE

    for f in features:
        p = f["properties"]
        p["block"] = norm(p.get("PCLBLOCK"))
        p["lot"] = norm(p.get("PCLLOT"))

    fc = {"type": "FeatureCollection", "features": features}
    city.parcels.parent.mkdir(parents=True, exist_ok=True)
    city.parcels.write_text(json.dumps(fc))
    print(f"wrote {city.parcels} — {len(features)} parcels, "
          f"{city.parcels.stat().st_size / 1e6:.1f} MB")
    return fc


if __name__ == "__main__":
    fetch_parcels(get_city(sys.argv[1] if len(sys.argv) > 1 else ""))
