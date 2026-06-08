"""Generate one published map page per ZIP at the repo root.

For every ZIP across all configured cities, renders <zip>.html (e.g. 07039.html,
07041.html, 07078.html) and an index.html landing page linking to them. These
are tracked + served by GitHub Pages.

Needs the per-city geocode caches and parcels (run src/geocode.py <city> and
src/fetch_parcels.py <city> first).

Usage: python3 src/build_pages.py
"""
from __future__ import annotations

import json

from build_map import build_map, load_segment
from config import CITIES, ROOT


def zip_pages() -> list[tuple[str, str]]:
    """Build a page per (city, zip); return [(zip, label)] for the index."""
    built = []
    for city in CITIES.values():
        parcels = json.loads(city.parcels.read_text()) if city.parcels.exists() else None
        for _, zc in city.localities:
            seg = load_segment(city, zip=zc)
            if seg.empty:
                print(f"skip {zc}: no sales")
                continue
            title = f"{city.geo_label(zc)} — {len(seg):,} sales"
            m = build_map(city, seg, parcels, title)
            out = ROOT / f"{zc}.html"
            m.save(str(out))
            print(f"wrote {out.name}: {len(seg):,} sales ({out.stat().st_size/1e6:.0f} MB)")
            built.append((zc, city.geo_label(zc)))
    return built


def write_index(pages: list[tuple[str, str]]) -> None:
    items = "\n".join(
        f'    <li><a href="{zc}.html">{label} — {zc}</a></li>' for zc, label in pages)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>NJ Sales Maps</title>
<style>body{{font:16px/1.5 sans-serif;max-width:640px;margin:3rem auto;padding:0 1rem}}
h1{{font-size:1.4rem}} li{{margin:.4rem 0}}</style></head>
<body><h1>Real-estate sales maps by ZIP</h1>
<p>Interactive maps of historical sales (clustered pins, price heatmap, parcel choropleth).</p>
<ul>
{items}
</ul></body></html>"""
    (ROOT / "index.html").write_text(html)
    print(f"wrote index.html ({len(pages)} ZIP pages)")


if __name__ == "__main__":
    write_index(zip_pages())
