# mls-analysis

Historical real-estate sales analysis for Livingston Township, NJ (ZIP 07039),
from county property records (~20K sales, 1983–2026).

## Live map

The interactive sales map is published via GitHub Pages: **`index.html`**
(clustered per-location pins, price heatmap, parcel choropleth, per-year layers,
address search + geocoder).

## Notebooks (`notebooks/`)

- `sales_trends.ipynb` — median price, volume, and $/sqft by year for a filtered segment.
- `property_lookup.ipynb` — sale history for one property (by address or block/lot).
- `sales_map.ipynb` — builds the interactive Folium map.
- `data_quality.ipynb` — record reconciliation (raw → clean → mappable) and a
  `diagnose()` tool for "why isn't X on the map?".

## Scripts

- `geocode.py` — geocodes addresses via the free US Census batch geocoder (cached).
- `fetch_parcels.py` — pulls NJOGIS parcel-boundary polygons for the choropleth.

## Data

Raw CSVs and geocode/parcel caches are **not** committed (they contain
buyer/seller names). The published map has its data inlined, so it works
standalone. To rebuild from scratch, place the county exports in `data/`, run
`geocode.py` and `fetch_parcels.py`, then run the notebooks.
