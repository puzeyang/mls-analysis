"""Fetch Livingston Township parcel-boundary polygons from NJOGIS.

Source: NJ Office of GIS "Parcels and MOD-IV Composite of NJ" hosted feature
service. Pulls only Livingston Twp (MUN_NAME='LIVINGSTON TWP', CD_CODE 0710) as
GeoJSON in WGS84 (lat/lon), paginated. Caches to output/parcels_livingston.geojson
so it's fetched once.

Each feature's properties carry normalized `block` / `lot` (leading zeros
stripped) so they join to merged.csv's Block/Lot. ~97% of sale parcels match.

Usage:
    python3 fetch_parcels.py
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

LAYER = ("https://services2.arcgis.com/XVOqAjTOJ5P6ngMu/arcgis/rest/services/"
         "Parcels_Composite_NJ_WM/FeatureServer/0/query")
OUT = Path("output/parcels_livingston.geojson")
PAGE = 2000


def norm(s) -> str:
    """Normalize a block/lot string to match merged.csv (strip leading zeros)."""
    s = str(s).strip()
    if "." in s:
        return s.lstrip("0")
    return s.lstrip("0") or "0"


def _fetch_page(offset: int) -> dict:
    q = urllib.parse.urlencode({
        "where": "MUN_NAME='LIVINGSTON TWP'",
        "outFields": "PAMS_PIN,PCLBLOCK,PCLLOT,PCLQCODE,PROP_LOC",
        "outSR": 4326,            # WGS84 lat/lon, matches the geocode cache
        "resultOffset": offset,
        "resultRecordCount": PAGE,
        "f": "geojson",
    })
    with urllib.request.urlopen(f"{LAYER}?{q}", timeout=120) as r:
        return json.load(r)


def fetch_parcels() -> dict:
    features = []
    offset = 0
    while True:
        page = _fetch_page(offset)
        fs = page.get("features", [])
        features.extend(fs)
        print(f"  fetched {len(features)} parcels...")
        if len(fs) < PAGE:
            break
        offset += PAGE

    for f in features:
        p = f["properties"]
        p["block"] = norm(p.get("PCLBLOCK"))
        p["lot"] = norm(p.get("PCLLOT"))

    fc = {"type": "FeatureCollection", "features": features}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(fc))
    print(f"wrote {OUT} — {len(features)} parcels, {OUT.stat().st_size/1e6:.1f} MB")
    return fc


if __name__ == "__main__":
    fetch_parcels()
