# mls-analysis

Historical real-estate sales analysis for Livingston Township, NJ (ZIP 07039),
from county property records (~20K sales, 1983–2026).

## Live maps

Published via GitHub Pages. `index.html` (repo root) is a landing page linking to
one interactive map **per ZIP** under `html/` — `html/07039.html` (Livingston),
`html/07041.html` (Millburn), `html/07078.html` (Short Hills) — each with
clustered per-location pins, a price heatmap, and a parcel choropleth. Regenerate
with `python3 src/build_pages.py`.

## Notebooks (`notebooks/`)

- `sales_trends.ipynb` — median price, volume, and $/sqft by year for a filtered segment.
- `property_lookup.ipynb` — sale history for one property (by address or block/lot).
- `sales_map.ipynb` — builds the interactive Folium map.
- `data_quality.ipynb` — record reconciliation (raw → clean → mappable) and a
  `diagnose()` tool for "why isn't X on the map?".

## Scripts (`src/`)

- `src/geocode.py` — geocodes addresses via the free US Census batch geocoder (cached).
- `src/fetch_parcels.py` — pulls NJOGIS parcel-boundary polygons for the choropleth.

## Data

Raw CSVs and geocode/parcel caches are **not** committed (they contain
buyer/seller names). The published map has its data inlined, so it works
standalone. To rebuild from scratch, place the county exports in `data/`, run
`python3 src/geocode.py` and `python3 src/fetch_parcels.py`, then run the notebooks.
