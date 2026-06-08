"""Geocode property addresses via the free US Census geocoder, per city.

No API key. Results are cached to output/<city>/geocode_cache.csv keyed by the
raw address string, so re-runs only fetch addresses not already cached. Uses the
Census *batch* endpoint (CSV upload, up to 10k rows/request) which is far faster
than per-address calls.

Usage:
    python3 src/geocode.py livingston      # or millburn
    from src.geocode import load_cache, geocode_addresses
    from src.config import get_city
"""
from __future__ import annotations

import csv
import io
import sys
import time
import urllib.request

import pandas as pd

from config import City, get_city

BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"
BATCH_SIZE = 5000  # Census allows up to 10k; smaller is more reliable


def load_cache(city: City) -> pd.DataFrame:
    """Return cached geocodes as a DataFrame[address, lat, lon, matched, zip]."""
    if city.geocode_cache.exists():
        return pd.read_csv(city.geocode_cache, dtype={"address": str, "zip": str})
    return pd.DataFrame(columns=["address", "lat", "lon", "matched", "zip"])


def _save_cache(city: City, df: pd.DataFrame) -> None:
    city.geocode_cache.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values("address").to_csv(city.geocode_cache, index=False)


def _geocode_batch(city: City, locality: tuple[str, str],
                   addresses: list[str]) -> dict[str, tuple[float | None, float | None]]:
    """POST one batch to the Census batch endpoint for one locality. {address: (lat, lon)}."""
    geo_city, zc = locality
    buf = io.StringIO()
    w = csv.writer(buf)
    for i, a in enumerate(addresses):
        w.writerow([i, a, geo_city, city.state, zc])  # id, street, city, state, zip
    payload = buf.getvalue().encode()

    boundary = "----censusbatch"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
        f"{BENCHMARK}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="addressFile"; filename="addrs.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        BATCH_URL, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        text = r.read().decode()

    out: dict[str, tuple[float | None, float | None]] = {}
    for row in csv.reader(io.StringIO(text)):
        # columns: id, input_address, match_status, match_type, matched_addr, "lon,lat", ...
        idx = int(row[0])
        addr = addresses[idx]
        if len(row) >= 6 and row[2] == "Match":
            lon, lat = row[5].split(",")
            out[addr] = (float(lat), float(lon))
        else:
            out[addr] = (None, None)
    return out


def _geocode_locality(city: City, locality: tuple[str, str],
                      addresses: list[str]) -> dict[str, tuple[float, float]]:
    """Geocode all `addresses` against one locality; return only the matches."""
    found: dict[str, tuple[float, float]] = {}
    for start in range(0, len(addresses), BATCH_SIZE):
        chunk = addresses[start:start + BATCH_SIZE]
        print(f"    {locality[0]} {locality[1]} — batch {start // BATCH_SIZE + 1}: {len(chunk)}...")
        for addr, (lat, lon) in _geocode_batch(city, locality, chunk).items():
            if lat is not None:
                found[addr] = (lat, lon)
        if start + BATCH_SIZE < len(addresses):
            time.sleep(1)  # be polite to the free service
    return found


def geocode_addresses(city: City, addresses: list[str]) -> pd.DataFrame:
    """Geocode `addresses` for `city`, using and updating its cache. Returns the cache.

    A township can span several postal localities, so unmatched addresses are
    retried against each of `city.localities` in turn.
    """
    cache = load_cache(city)
    known = set(cache["address"])
    todo = sorted({a.strip() for a in addresses if a and a.strip()} - known)
    print(f"[{city.name}] {len(addresses)} requested, {len(known)} cached, {len(todo)} to fetch")

    matches: dict[str, tuple[float, float, str]] = {}
    remaining = list(todo)
    for locality in city.localities:
        if not remaining:
            break
        found = _geocode_locality(city, locality, remaining)
        # tag each match with the ZIP of the locality that matched it
        matches.update({a: (lat, lon, locality[1]) for a, (lat, lon) in found.items()})
        remaining = [a for a in remaining if a not in found]
        print(f"  after {locality[0]}: {len(found)} matched, {len(remaining)} still missing")

    new_rows = [{"address": a,
                 "lat": matches.get(a, (None, None, None))[0],
                 "lon": matches.get(a, (None, None, None))[1],
                 "matched": a in matches,
                 "zip": matches.get(a, (None, None, None))[2]} for a in todo]
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        cache = new_df if cache.empty else pd.concat([cache, new_df], ignore_index=True)
        _save_cache(city, cache)

    hit = cache["matched"].sum()
    print(f"cache now {len(cache)} addresses, {hit} matched ({hit / len(cache):.0%})")
    return cache


if __name__ == "__main__":
    city = get_city(sys.argv[1] if len(sys.argv) > 1 else "")
    df = pd.read_csv(city.data, dtype=str)
    addrs = df["Property Address"].dropna().str.strip().unique().tolist()
    geocode_addresses(city, addrs)
