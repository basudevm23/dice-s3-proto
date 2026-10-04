# %% [markdown]
# # Step 2.1 - Clean the order data and add geography
# Input : data/raw/amazon_sale_report.csv, data/raw/pincode_directory.csv
# Output: data/processed/orders_clean.csv      (one row per order line)
#         data/processed/district_summary.csv  (one row per PIN district)
#
# Adds: pin3 (India Post sorting district = first 3 PIN digits), district name and lat/long
#       (used to place orders on a map in the prototypes).
# Note: we do NOT invent hub locations. Valmo's real hub map isn't public, so the case pack's
#       distance bands (15/17/22% RTO) are used only as stated figures, not mapped onto pincodes.

# %%
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import RAW, PROCESSED  # noqa: E402
from config import RETURNED_STATUSES, CANCELLED_STATUSES  # noqa: E402

# %% Load and normalise column names (Kaggle original and mirror use different styles)
df = pd.read_csv(RAW / "amazon_sale_report.csv", low_memory=False)
df.columns = (df.columns.str.strip().str.lower()
              .str.replace("-", "_").str.replace(" ", "_"))
df = df.rename(columns={"date": "order_date"})
df = df.loc[:, ~df.columns.str.startswith("unnamed")]

df["order_date"] = pd.to_datetime(df["order_date"], format="mixed", errors="coerce")
df = df.dropna(subset=["order_date", "ship_postal_code", "sku"])
df["pin"] = df["ship_postal_code"].astype(float).astype(int).astype(str).str.zfill(6)
df["pin3"] = df["pin"].str[:3]
df["size"] = df["size"].astype(str).str.upper().str.strip()
df["category"] = df["category"].astype(str).str.strip().str.title()
df["is_cancelled"] = df["status"].isin(CANCELLED_STATUSES)
df["is_returned"] = df["status"].isin(RETURNED_STATUSES)
df["is_delivered"] = df["status"].eq("Shipped - Delivered to Buyer")
print(f"{len(df):,} order lines, {df['order_date'].min().date()} to {df['order_date'].max().date()}")

# %% Pincode directory -> district name + coordinates
pc = pd.read_csv(RAW / "pincode_directory.csv", low_memory=False, encoding_errors="ignore")
pc["pin"] = pc["Pincode"].astype(str).str.zfill(6)
pc["lat"] = pd.to_numeric(pc["Latitude"], errors="coerce")
pc["lon"] = pd.to_numeric(pc["Longitude"], errors="coerce")
pc = pc[(pc["lat"].between(6, 38)) & (pc["lon"].between(68, 98))]   # drop bad geocodes
pin_geo = pc.groupby("pin").agg(lat=("lat", "median"), lon=("lon", "median"),
                                district=("District", "first"), state=("StateName", "first")).reset_index()

df = df.merge(pin_geo, on="pin", how="left")
print(f"geocoded {df['lat'].notna().mean():.0%} of orders")

# %% Save
keep = ["order_id", "order_date", "status", "fulfilment", "style", "sku", "category", "size", "qty", "amount",
        "ship_city", "ship_state", "pin", "pin3", "district", "lat", "lon", "is_cancelled", "is_returned", "is_delivered"]
df[keep].to_csv(PROCESSED / "orders_clean.csv", index=False)

days = (df["order_date"].max() - df["order_date"].min()).days + 1
live = df[~df["is_cancelled"]]
summary = (live.groupby("pin3").agg(
    district=("district", lambda s: s.mode().iat[0] if s.notna().any() else ""),
    orders=("order_id", "count"), skus=("sku", "nunique"), styles=("style", "nunique"),
    pincodes=("pin", "nunique"), returned=("is_returned", "sum"))
    .assign(orders_per_day=lambda x: (x["orders"] / days).round(2))
    .sort_values("orders", ascending=False))
summary.to_csv(PROCESSED / "district_summary.csv")
print(summary.head(10))
print("\nKanpur / Lucknow / Bengaluru:")
print(summary.loc[[p for p in ["208", "226", "560"] if p in summary.index]])
print("\nNext: python step3_analysis/07_backtest_match_rate.py")
