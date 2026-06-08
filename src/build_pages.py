"""Generate one published map page per ZIP under html/, plus a root index.html.

For every ZIP across all configured cities, renders html/<zip>.html (e.g.
html/07039.html, html/07041.html, html/07078.html) and an index.html landing
page at the repo root linking to them. Both are tracked + served by GitHub Pages
(html/ is a tracked subfolder — NOT output/, which is gitignored).

Needs the per-city geocode caches and parcels (run src/geocode.py <city> and
src/fetch_parcels.py <city> first).

Usage: python3 src/build_pages.py
"""
from __future__ import annotations

import json

from build_map import build_map, load_all, load_segment
from config import CITIES, ROOT

HTML_DIR = ROOT / "html"


def zip_pages() -> list[tuple[str, str]]:
    """Build a page per (city, zip) under html/; return [(zip, label)] for the index."""
    HTML_DIR.mkdir(exist_ok=True)
    built = []
    for city in CITIES.values():
        parcels = json.loads(city.parcels.read_text()) if city.parcels.exists() else None
        full = load_all(city)   # backs the address search (every year/zip/class)
        for _, zc in city.localities:
            seg = load_segment(city, zip=zc)
            if seg.empty:
                print(f"skip {zc}: no sales")
                continue
            title = f"{city.geo_label(zc)} — {len(seg):,} sales"
            m = build_map(city, seg, parcels, title, search_df=full)
            out = HTML_DIR / f"{zc}.html"
            m.save(str(out))
            print(f"wrote {out.relative_to(ROOT)}: {len(seg):,} sales ({out.stat().st_size/1e6:.0f} MB)")
            built.append((zc, city.geo_label(zc)))
    return built


def write_index(pages: list[tuple[str, str]]) -> None:
    items = "\n".join(
        f'    <li><a href="html/{zc}.html">{label} — {zc}</a></li>' for zc, label in pages)
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
    print(f"wrote index.html ({len(pages)} ZIP pages, linking into html/)")


if __name__ == "__main__":
    write_index(zip_pages())
