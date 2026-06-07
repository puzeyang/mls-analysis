"""Geocode Livingston Township property addresses via the free US Census geocoder.

No API key. Results are cached to output/geocode_cache.csv keyed by the raw
address string, so re-runs only fetch addresses not already cached. Uses the
Census *batch* endpoint (CSV upload, up to 10k rows/request) which is far faster
than per-address calls.

Usage:
    python3 src/geocode.py        # geocode all unique addresses in data/merged.csv
    from src.geocode import load_cache, geocode_addresses
"""
from __future__ import annotations

import csv
import io
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # repo root (src/ lives under it)
DATA = ROOT / "data" / "merged.csv"
CACHE = ROOT / "output" / "geocode_cache.csv"
CITY, STATE, ZIP = "Livingston", "NJ", "07039"
BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"
BATCH_SIZE = 5000  # Census allows up to 10k; smaller is more reliable


def load_cache() -> pd.DataFrame:
    """Return cached geocodes as a DataFrame[address, lat, lon, matched]."""
    if CACHE.exists():
        return pd.read_csv(CACHE, dtype={"address": str})
    return pd.DataFrame(columns=["address", "lat", "lon", "matched"])


def _save_cache(df: pd.DataFrame) -> None:
    CACHE.parent.mkdir(exist_ok=True)
    df.sort_values("address").to_csv(CACHE, index=False)


def _geocode_batch(addresses: list[str]) -> dict[str, tuple[float | None, float | None]]:
    """POST one batch to the Census batch endpoint. Returns {address: (lat, lon)}."""
    buf = io.StringIO()
    w = csv.writer(buf)
    for i, a in enumerate(addresses):
        w.writerow([i, a, CITY, STATE, ZIP])  # unique id, street, city, state, zip
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


def geocode_addresses(addresses: list[str]) -> pd.DataFrame:
    """Geocode `addresses`, using and updating the on-disk cache. Returns the cache."""
    cache = load_cache()
    known = set(cache["address"])
    todo = sorted({a.strip() for a in addresses if a and a.strip()} - known)
    print(f"{len(addresses)} requested, {len(known)} cached, {len(todo)} to fetch")

    new_rows = []
    for start in range(0, len(todo), BATCH_SIZE):
        chunk = todo[start:start + BATCH_SIZE]
        print(f"  batch {start // BATCH_SIZE + 1}: {len(chunk)} addresses...")
        result = _geocode_batch(chunk)
        for addr, (lat, lon) in result.items():
            new_rows.append({"address": addr, "lat": lat, "lon": lon,
                             "matched": lat is not None})
        if start + BATCH_SIZE < len(todo):
            time.sleep(1)  # be polite to the free service

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        cache = new_df if cache.empty else pd.concat([cache, new_df], ignore_index=True)
        _save_cache(cache)

    hit = cache["matched"].sum()
    print(f"cache now {len(cache)} addresses, {hit} matched ({hit / len(cache):.0%})")
    return cache


if __name__ == "__main__":
    df = pd.read_csv(DATA, dtype=str)
    addrs = df["Property Address"].dropna().str.strip().unique().tolist()
    geocode_addresses(addrs)
