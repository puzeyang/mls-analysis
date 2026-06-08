"""Build a Folium sales map for a city, optionally scoped to one ZIP.

Shared by the sales_map notebook's logic and src/build_pages.py. Mirrors the
notebook: clustered per-location pins (popup lists every sale), price heatmap,
and a parcel choropleth. Pins use DivIcon markers so MarkerCluster spiderfy can
separate near-overlapping points.
"""
from __future__ import annotations

import json

import branca.colormap as cm
import folium
import pandas as pd
from folium.features import DivIcon
from folium.plugins import HeatMap, MarkerCluster

from config import City


def load_segment(city: City, zip: str | None = None,
                 property_class: str | None = "__residential__",
                 year_min: int | None = 2000) -> pd.DataFrame:
    """Clean, geocoded, optionally ZIP/class/year-scoped sales for `city`."""
    df = pd.read_csv(city.data, dtype=str)
    cache = pd.read_csv(city.geocode_cache, dtype={"address": str, "zip": str})

    df["sale_date"] = pd.to_datetime(df["Sale Date"], format="%m/%d/%Y", errors="coerce")
    df["price"] = pd.to_numeric(df["Sale Price"], errors="coerce")
    df["beds"] = pd.to_numeric(df["Beds"], errors="coerce")
    df["year"] = df["sale_date"].dt.year
    df["addr"] = df["Property Address"].str.strip()

    def norm(s):
        s = "" if pd.isna(s) else str(s).strip()
        return s.lstrip("0") if "." in s else (s.lstrip("0") or "0")

    df["block"] = df["Block"].map(norm)
    df["lot"] = df["Lot"].map(norm)

    df = df[df["sale_date"].notna() & (df["price"] >= 1000)]
    df = df.merge(cache[cache["matched"]][["address", "lat", "lon", "zip"]],
                  left_on="addr", right_on="address", how="inner")

    if property_class == "__residential__":
        property_class = city.residential_class
    if property_class is not None:
        df = df[df["Property Class"] == property_class]
    if year_min is not None:
        df = df[df["year"] >= year_min]
    if zip is not None:
        df = df[df["zip"] == str(zip)]
    return df


def build_map(city: City, seg: pd.DataFrame, parcels: dict | None,
              title: str) -> folium.Map:
    """Render the clustered-pin + heatmap + choropleth map for `seg`."""
    q1, q2, q3 = seg["price"].quantile([0.25, 0.5, 0.75])

    def color(p):
        return ("green" if p < q1 else "lightgreen" if p < q2
                else "orange" if p < q3 else "red")

    def dot(c):
        return DivIcon(icon_size=(14, 14), icon_anchor=(7, 7),
                       html=f'<div style="width:12px;height:12px;border-radius:50%;'
                            f'background:{c};border:1px solid #333;opacity:0.85"></div>')

    def popup(g):
        multi = g["addr"].nunique() > 1
        lines = [(f"{r['addr']} &middot; " if multi else "") +
                 f"{r['sale_date']:%Y-%m-%d}: ${r['price']:,.0f} "
                 f"({r['Beds']}bd/{r['Baths']}ba)" for _, r in g.iterrows()]
        head = g["addr"].iloc[0] if not multi else f"{g['addr'].nunique()} addresses / {len(g)} sales"
        return f"<b>{head}</b><br>" + "<br>".join(lines)

    m = folium.Map(location=[seg["lat"].median(), seg["lon"].median()],
                   zoom_start=14, tiles="cartodbpositron")
    folium.map.Marker(
        [seg["lat"].max(), seg["lon"].median()],
        icon=DivIcon(html=f'<div style="font:600 14px sans-serif;background:white;'
                          f'padding:3px 7px;border:1px solid #999;border-radius:4px">{title}</div>'),
    ).add_to(m)

    cluster = MarkerCluster(name="Sales (clustered)").add_to(m)
    for (lat, lon), g in seg.groupby(["lat", "lon"]):
        g = g.sort_values("sale_date")
        folium.Marker([lat, lon], icon=dot(color(g["price"].iloc[-1])),
                      popup=folium.Popup(popup(g), max_width=300)).add_to(cluster)

    HeatMap([[r["lat"], r["lon"], r["price"]] for _, r in seg.iterrows()],
            name="Price heatmap", radius=15, blur=20, show=False).add_to(m)

    if parcels:
        agg = (seg.groupby(["block", "lot"])
                  .agg(median_price=("price", "median"), sales=("price", "size")).reset_index())
        agg["key"] = agg["block"] + "_" + agg["lot"]
        stats = agg.set_index("key")[["median_price", "sales"]].to_dict("index")
        feats = [{**f, "properties": {**f["properties"], **stats[k]}}
                 for f in parcels["features"]
                 if (k := f"{f['properties']['block']}_{f['properties']['lot']}") in stats]
        if feats:
            lo, hi = agg["median_price"].quantile([0.05, 0.95])
            cmap = cm.linear.YlOrRd_09.scale(lo, hi)
            cmap.caption = "Median sale price ($)"
            folium.GeoJson(
                {"type": "FeatureCollection", "features": feats},
                name="Median price by parcel", show=False,
                style_function=lambda ft: {"fillColor": cmap(ft["properties"]["median_price"]),
                                           "color": "#555", "weight": 0.5, "fillOpacity": 0.7},
                tooltip=folium.GeoJsonTooltip(fields=["PROP_LOC", "median_price", "sales"],
                                              aliases=["Address", "Median price", "# sales"],
                                              localize=True),
            ).add_to(m)
            cmap.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m
