# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Analyzes **MLS / county real-estate sales records** to surface historical sales
trends for a geography (city/township, ZIP, neighborhood) — price trends over
time, volume, $/sqft — and presents results as reports and on maps.

### Data — multi-city

Data is organized **per city** under `data/<city>/`, with **`data/<city>/merged.csv`**
as the canonical input. `src/config.py` defines each city (data path, geocoder
localities, parcel `MUN_NAME`/`CD_CODE`, and per-city `output/<city>/` paths);
pick one with `get_city("livingston" | "millburn")`. To add a city, append to
`CITIES` in config.py.

All cities are normalized to the **same 19 columns**: `Property Address, Block,
Lot, Qual, Sale Date, Sale Price, Acreage, Sq Ft, Buyer Name, Seller Name,
Property Class, Zoning, Beds, Baths, Year Built, Total Rooms, Land Value,
Building Value, Property URL`. `Sale Date` is `MM/DD/YYYY`; `Sale Price` is an
unformatted integer.

- **livingston** — `data/livingston/*.csv` from a county property DB
  (`stateinfoservice.com`), Essex/Livingston (07039), ~1983–2026, ~20K rows.
  `data/livingston/merged.csv` = the raw CSVs concatenated + de-duped on the full
  row. `Property Class` uses "Residential"/"Commercial"/…; `Property URL` embeds
  parcel id `0710_<block>_<lot>`.
- **millburn** — `data/millburn/*.xls` are GSMLS broker exports (212 cols, listings).
  `src/merge_millburn.py` reads them, keeps **closed sales only** (SalesPrice +
  ClosedDate), de-dupes to latest per MlsNum, and **maps to the 19-col schema**
  (`data/millburn/merged.csv`, ~7.5K sales, 2000–2026). Caveats: no Buyer/Seller
  names (not in export); `Sq Ft` sparse (~18%); `Property Class` is `SubPropType`
  (`SinglFam`/`CCT`/blank — so use `property_class="SinglFam"` or `None`, not
  "Residential"); Millburn Twp spans Millburn 07041 **and Short Hills 07078**
  (geocoder tries both).

Data notes / gotchas (general):

- **No ZIP/city column** in `merged.csv` — geography is implied by the export.
  ZIP is **recovered from the geocoder**: `geocode.py` records which locality
  matched each address (its `zip` column in `geocode_cache.csv`), so the
  notebooks join that on to enable a `zip` FILTER. Livingston is all 07039;
  Millburn splits 07041 (Millburn) / 07078 (Short Hills) — and Short Hills runs
  far pricier (2024 SF median ~$2.19M vs Millburn ~$1.33M), so the ZIP split
  matters. `Block`+`Lot`(+`Qual`) key a parcel; re-sales appear as multiple
  rows. Block/Lot are often zero-padded (`05100` vs `5100`) — `norm()` strips
  leading zeros to join.
- Addresses are free-form/unnormalized (`82 Ridge Dr` vs `Drive`).
- Placeholder/non-arms-length rows exist (`REDACTED`, `$0`/nominal sales,
  `YearBuilt=9999`) — filtered for trend analysis.

### Code

(Greenfield — no analysis package exists yet. When building it, prefer pandas
for loading/aggregation; keep loaders, trend aggregation, reporting, and mapping
as separate modules. Geocoding for the map layer will likely need an external
service or a cached geocode table keyed by parcel/address.)

**Direction (chosen):** primary interface is a **Jupyter notebook** for
interactive trend analysis + reports, with an interactive **Folium** map layer.
All scripts take a city arg (`python3 src/<script>.py <city>`); notebooks set
`CITY = get_city("<city>")` in their first cell. Caches/outputs are per-city
under `output/<city>/`.

Geocoding: `src/geocode.py <city>` resolves addresses to lat/lon via the **free
US Census batch geocoder** (no API key; results are storable), caching to
`output/<city>/geocode_cache.csv` keyed by raw address — re-runs only fetch new
addresses. A city can list several geocoder localities (city/zip) that are tried
in turn, since a township can span postal areas (Millburn → Millburn 07041 +
Short Hills 07078, lifting its match from 31% → 99%). Livingston ~96% unique /
~97% rows. (Census over Google Maps: Google needs a billing key and its ToS
forbids caching/displaying geocodes off Google maps.)

Parcel polygons: `src/fetch_parcels.py <city>` pulls the township's tax-lot
boundaries from the **NJOGIS "Parcels and MOD-IV Composite"** hosted service (no
key) as GeoJSON in WGS84, caching to `output/<city>/parcels.geojson` (queried by
the city's `MUN_NAME`). Join key is `Block`+`Lot` after **stripping leading
zeros**; ~97% of Livingston sale parcels match.

- `notebooks/sales_trends.ipynb` — loads `merged.csv`, cleans (drops
  unparseable dates + non-arms-length sales priced `< $1,000`), filters a
  segment (property class / year range / beds via the `FILTERS` cell), and plots
  median price, sales volume, and median $/sqft by year. Also a **monthly**
  section: a year-month time series, a calendar-month **seasonality** view (sales
  peak Jun–Aug, trough in winter), **year-over-year** price change (same month
  vs. a year earlier; raw monthly YoY is noisy at ~30 sales/mo so a 12-mo
  rolling-median YoY is shown alongside), and a **% vs. prior year-end** heat
  table (each month's median vs. the prior calendar year's median, year×month,
  last 20 years + an `Avg` row; earlier years excluded — too few sales/month to
  be stable) and the same **pooled into 3-month seasons** (Dec–Feb, Mar–May,
  Jun–Aug, Sep–Nov; winter labeled by ending year so Dec comes from the prior
  calendar year; each season = one pooled median). Exports the yearly summary to
  `output/`.
- `notebooks/data_quality.ipynb` — reconciliation: the record funnel (raw →
  clean → mappable), per-reason drop counts (bad date / missing price / `<$1,000`
  / not geocoded), the list of addresses that fail to geocode, and a
  `diagnose(address, **filters)` helper that explains, per sale, exactly why a
  property is or isn't on the map. Its `clean`/`mappable` counts reconcile with
  the trends & map notebooks (incl. treating missing/non-numeric prices as
  non-arms-length — `NaN < 1000` is False, so they'd otherwise slip the filter).
  Use it to answer \"why isn't X on the map\" — usually an active FILTER (e.g.
  77 Sycamore's only real sale was 2013, hidden by the default `year_min=2020`),
  not bad data.
- `notebooks/property_lookup.ipynb` — sale history for a single property:
  `by_address()` (case-insensitive, **word-boundary** match so `4 Blackstone`
  doesn't catch `14/24 Blackstone`), `by_block_lot(block, lot, qual)` (exact
  parcel key; `Qual` separates condo units sharing a block/lot), and `history()`
  (appreciation/CAGR between consecutive arms-length sales; **raises** if handed
  a multi-parcel result, since chaining different houses is meaningless). Note:
  the `< $1,000` filter catches obvious $0–$10 transfers but not nominal
  "real-ish" intra-family amounts, which can still distort a parcel's CAGR.
- `notebooks/sales_map.ipynb` — interactive Folium map of geocoded sales
  (joins `merged.csv` to `output/geocode_cache.csv`). Same `FILTERS` cell as the
  trends notebook (incl. year range). Layer-control layers (top-right): clustered
  pins **grouped one-per-location** (most sale coordinates hold >1 sale — repeat
  sales of a parcel, or condo units geocoded to the same building point — so a
  per-sale map stacks markers and only the top is clickable; the popup instead
  lists every sale at that point, colored by the latest sale's quartile). Pins
  are `folium.Marker` w/ a colored `DivIcon` dot, **not `CircleMarker`** —
  MarkerCluster's spiderfy only repositions `L.marker`, so CircleMarkers at
  near-identical coords stay overlapped and unclickable. A price heatmap
  (per-sale), and a **parcel choropleth** (median
  price per lot, from `output/parcels_livingston.geojson`, only parcels with
  sales in the current segment are drawn). Plus **per-year layers** — one
  `Sales <year>` checkbox per year in the layer control (additive; tick several
  to compare), **capped to `CHECKBOX_YEARS` (default 2020–2026)** so the control
  stays short even though the data/pins go back further. So year can be filtered
  two ways: the checkboxes (recent years) or the `FILTERS` cell
  (`year_min`/`year_max`, scopes the whole map; default `year_min=2000`). Two **search
  boxes** (top-left): a `Search` over a hidden GeoJson of **all** geocoded sale
  addresses (built from the full `df`, *not* the filtered segment — so a property
  hidden by the active filters is still findable; it zooms there even if its pin
  isn't drawn) and a `Geocoder` (Nominatim) that drops a marker on *any* typed
  address, in the data or not. Saves standalone HTML to `output/`. Needs
  `folium` (`python3 -m pip install folium`). The geocoder's custom JS renders
  in a browser-opened HTML but may be sandboxed out of the inline notebook
  output — re-run all cells and open `output/map_*.html`.

---

## Behavioral guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
