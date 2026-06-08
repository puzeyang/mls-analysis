"""Merge Millburn GSMLS .xls broker exports into the Livingston schema.

The Millburn exports (data/millburn/*.xls) are GSMLS listing dumps: 212 columns,
one row per listing, many non-sales (withdrawn/expired/active). This:

  - reads all .xls (needs xlrd),
  - keeps only CLOSED SALES (SalesPrice + ClosedDate present),
  - de-dupes to the latest row per MlsNum (same listing can recur across files),
  - maps to the same 19 columns the Livingston notebooks use, so the existing
    analysis works on Millburn too.

Writes data/millburn/merged.csv. Run: python3 src/merge_millburn.py
"""
from __future__ import annotations

import glob
import warnings
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "millburn"
OUT = SRC_DIR / "merged.csv"

# Livingston canonical columns (output schema)
COLUMNS = ["Property Address", "Block", "Lot", "Qual", "Sale Date", "Sale Price",
           "Acreage", "Sq Ft", "Buyer Name", "Seller Name", "Property Class",
           "Zoning", "Beds", "Baths", "Year Built", "Total Rooms",
           "Land Value", "Building Value", "Property URL"]


def _clean(s: pd.Series) -> pd.Series:
    """Strip whitespace and the trailing '*' markers GSMLS leaves on many fields."""
    return s.astype("string").str.strip().str.rstrip("*").str.strip()


def load_closed_sales() -> pd.DataFrame:
    files = sorted(glob.glob(str(SRC_DIR / "*.xls")))
    if not files:
        raise SystemExit(f"no .xls files in {SRC_DIR}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = pd.concat([pd.read_excel(f) for f in files], ignore_index=True)
    print(f"{len(files)} files, {len(raw):,} rows")

    closed = raw[raw["SalesPrice"].notna() & raw["ClosedDate"].notna()].copy()
    print(f"closed sales: {len(closed):,}")

    # latest row per listing (LastModified is a full timestamp)
    closed["_mod"] = pd.to_datetime(closed["LastModified"], errors="coerce")
    closed = (closed.sort_values("_mod")
                    .drop_duplicates("MlsNum", keep="last"))
    print(f"after de-dup to latest per MlsNum: {len(closed):,}")
    return closed


def to_livingston_schema(d: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=d.index)

    num = _clean(d["StreetNumDisplay"])
    street = _clean(d["StreetName"])
    unit = _clean(d["UnitNum"])
    addr = (num.fillna("") + " " + street.fillna("")).str.strip()
    addr = addr.where(unit.isna(), addr + " #" + unit.fillna(""))
    out["Property Address"] = addr

    out["Block"] = _clean(d["BlockID"])
    out["Lot"] = _clean(d["LotID"])
    out["Qual"] = pd.NA
    out["Sale Date"] = pd.to_datetime(d["ClosedDate"], errors="coerce").dt.strftime("%m/%d/%Y")
    out["Sale Price"] = pd.to_numeric(d["SalesPrice"], errors="coerce")
    out["Acreage"] = pd.to_numeric(_clean(d["Acres"]), errors="coerce")
    out["Sq Ft"] = pd.to_numeric(d["SqFtApprox"], errors="coerce")
    out["Buyer Name"] = pd.NA      # not in GSMLS export
    out["Seller Name"] = pd.NA     # OwnerName is mostly "on file"/agent text
    out["Property Class"] = _clean(d["SubPropType"])
    out["Zoning"] = _clean(d["Zoning"])
    out["Beds"] = pd.to_numeric(d["Beds"], errors="coerce")
    out["Baths"] = pd.to_numeric(d["BathsTotal"], errors="coerce")
    yb = pd.to_numeric(d["YearBuilt"], errors="coerce")
    out["Year Built"] = yb.where((yb > 1700) & (yb <= 2026))  # 9999/0 are "unknown"
    out["Total Rooms"] = pd.to_numeric(d["Rooms"], errors="coerce")
    out["Land Value"] = pd.to_numeric(d["AssessAmountLand"], errors="coerce")
    out["Building Value"] = pd.to_numeric(d["AssessAmountBldg"], errors="coerce")
    out["Property URL"] = _clean(d["TaxId"])   # no URL; parcel TaxId is the closest id
    return out[COLUMNS]


if __name__ == "__main__":
    df = to_livingston_schema(load_closed_sales())
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT} — {len(df):,} closed sales, {len(df.columns)} columns")
    d = pd.to_datetime(df["Sale Date"], format="%m/%d/%Y", errors="coerce")
    print(f"date range: {d.min():%Y-%m-%d} .. {d.max():%Y-%m-%d}")
