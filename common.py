"""common.py - helpers shared by every step."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
for p in (RAW, PROCESSED, OUTPUTS):
    p.mkdir(parents=True, exist_ok=True)


def wilson(successes, n, z=1.96):
    """95% confidence interval for a proportion (works for small n)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_orders():
    path = PROCESSED / "orders_clean.csv"
    if not path.exists():
        raise FileNotFoundError("Run step2_prepare/04_prepare_orders.py first.")
    df = pd.read_csv(path, dtype={"pin": str, "pin3": str}, parse_dates=["order_date"])
    return df


def save_json(obj, path):
    path = Path(path)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=float))
    print(f"saved {path.relative_to(ROOT)}")


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def scale_match(p, k):
    """If demand for the identical item is k times larger, chance of a match = 1-(1-p)^k."""
    return 1 - (1 - p) ** k


class DemandModel:
    """
    Estimates daily demand for one exact item (style + size) in one district,
    using only the history BEFORE a given day (no peeking at the future):

        demand = (orders of this style in the district in the last H days / H)
                 x (share of this size among all orders of the style, nationally)

    Style-level history is far less sparse than size-level history, and size shares
    are stable, so this is steadier than counting the exact SKU alone.
    """

    def __init__(self, orders, history_days=30):
        self.h = history_days
        live = orders[~orders["is_cancelled"]]
        self.by_style_area = {k: np.sort(g["order_date"].values)
                              for k, g in live.groupby(["style", "pin3"])}
        size_counts = live.groupby(["style", "size"]).size()
        style_counts = live.groupby("style").size()
        self.size_share = (size_counts / style_counts.reindex(size_counts.index.get_level_values(0)).values).to_dict()
        overall = live["size"].value_counts(normalize=True)
        self.overall_size_share = overall.to_dict()

    def daily_demand(self, style, size, pin3, day):
        arr = self.by_style_area.get((style, pin3))
        if arr is None:
            return 0.0
        day = np.datetime64(day)
        lo = day - np.timedelta64(self.h, "D")
        n = int(((arr >= lo) & (arr < day)).sum())
        share = self.size_share.get((style, size), self.overall_size_share.get(size, 0.0))
        return n / self.h * share

    @staticmethod
    def p_match(daily_demand, window_days, k=1):
        return 1 - math.exp(-daily_demand * k * window_days)
