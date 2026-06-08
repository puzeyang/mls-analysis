"""Per-city configuration for the MLS analysis.

Pick a city by name; everything (data path, geocoder params, parcel layer query,
and per-city output paths) is derived from here so the scripts and notebooks can
work on any configured city.

Data lives in `data/<city>/merged.csv`; outputs go to `output/<city>/`.

Add a city by appending an entry to CITIES.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class City:
    name: str            # slug, e.g. "livingston"
    label: str           # display, e.g. "Livingston Township (07039)"
    state: str
    mun_name: str        # NJOGIS parcel layer MUN_NAME
    cd_code: str         # NJ county+muni code
    # Census geocoder localities to try, in order. A township can span several
    # postal places (e.g. Millburn Twp includes Short Hills 07078), so geocoding
    # retries each (city, zip) until an address matches.
    localities: tuple[tuple[str, str], ...] = ()
    # Default `Property Class` value for the notebooks' residential filter. The
    # county data uses "Residential"; the GSMLS export uses "SinglFam". None = no
    # class filter.
    residential_class: str | None = None

    @property
    def data(self) -> Path:
        return ROOT / "data" / self.name / "merged.csv"

    @property
    def out_dir(self) -> Path:
        return ROOT / "output" / self.name

    @property
    def geocode_cache(self) -> Path:
        return self.out_dir / "geocode_cache.csv"

    @property
    def parcels(self) -> Path:
        return self.out_dir / "parcels.geojson"


CITIES = {
    "livingston": City(
        name="livingston", label="Livingston Township (07039)",
        state="NJ", mun_name="LIVINGSTON TWP", cd_code="0710",
        localities=(("Livingston", "07039"),),
        residential_class="Residential",
    ),
    "millburn": City(
        name="millburn", label="Millburn Township (07041)",
        state="NJ", mun_name="MILLBURN TWP", cd_code="0712",
        # Millburn Twp spans Millburn (07041) and Short Hills (07078).
        localities=(("Millburn", "07041"), ("Short Hills", "07078")),
        residential_class="SinglFam",
    ),
}


def get_city(name: str) -> City:
    key = (name or "").strip().lower()
    if key not in CITIES:
        raise SystemExit(f"unknown city {name!r}; choose from {sorted(CITIES)}")
    return CITIES[key]
