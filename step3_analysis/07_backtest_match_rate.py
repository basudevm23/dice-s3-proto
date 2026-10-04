# %% [markdown]
# # Step 3 - The evidence: would refused parcels find a nearby buyer?
# Input : data/processed/orders_clean.csv
# Output: outputs/match_rates.csv          how often a returned item is re-ordered nearby (by area and window)
#         outputs/district_match_rates.csv the same for each PIN district (7 days)
#         outputs/rule_calibration.csv     predicted vs actual chance of a match
#         outputs/policy_comparison.csv    cost per refused parcel: return all / hold all / hold by rule
#         outputs/model_vs_measured.csv    our formula vs the measured rate, per district
#         outputs/*.png                    charts for slides
#
# Honesty rules built in
# * A returned parcel is counted only if its whole waiting window lies inside the dataset (no cut-off bias).
# * A new order can be used by only one held parcel (no double counting).
# * The parcel's own order is never counted as its match.
# * The hold-or-return rule only sees the 30 days BEFORE the refusal (no peeking at the future).

# %%
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import OUTPUTS, load_orders, wilson, DemandModel  # noqa: E402
from config import COST, HOLDING, REFUSAL_LAG_DAYS, HISTORY_DAYS, DISTRICTS  # noqa: E402

orders = load_orders()
live = orders[~orders["is_cancelled"]].copy()
END = orders["order_date"].max()
START = orders["order_date"].min()
ret = orders[orders["is_returned"]].copy()
ret["refusal_day"] = ret["order_date"] + pd.Timedelta(days=REFUSAL_LAG_DAYS)
print(f"{len(live):,} live orders, {len(ret):,} returned parcels")


# %% Matching with one-use-per-order
def match(parcels, area, window):
    """For each parcel, the earliest unused same-SKU order in the same area within the window."""
    pool = {k: (g["order_date"].values, g["order_id"].values) for k, g in live.sort_values("order_date").groupby(["sku", area])}
    used = set()
    found = {}
    for idx, p in parcels.sort_values("refusal_day").iterrows():
        key = (p["sku"], p[area])
        if key not in pool:
            found[idx] = False
            continue
        dates, ids = pool[key]
        lo, hi = np.datetime64(p["refusal_day"]), np.datetime64(p["refusal_day"] + pd.Timedelta(days=window))
        hit = False
        for j in np.where((dates > lo) & (dates <= hi))[0]:
            if ids[j] != p["order_id"] and (key, j) not in used:
                used.add((key, j))
                hit = True
                break
        found[idx] = hit
    return pd.Series(found)


rows = []
AREAS = {"pin": "Same pincode", "pin3": "Same PIN district", "ship_city": "Same city", "ship_state": "Same state"}
for w in (3, 7, 14):
    eligible = ret[ret["refusal_day"] + pd.Timedelta(days=w) <= END]
    for area, label in AREAS.items():
        m = match(eligible, area, w)
        k, n = int(m.sum()), len(m)
        lo, hi = wilson(k, n)
        rows.append({"area": label, "window_days": w, "parcels": n, "matched": k,
                     "match_rate": round(k / n, 3), "low_95": round(lo, 3), "high_95": round(hi, 3)})
match_rates = pd.DataFrame(rows)
match_rates.to_csv(OUTPUTS / "match_rates.csv", index=False)
print(match_rates.pivot(index="area", columns="window_days", values="match_rate"))

# %% Per district (7 days)
W = 7
elig7 = ret[ret["refusal_day"] + pd.Timedelta(days=W) <= END].copy()
elig7["matched"] = match(elig7, "pin3", W)
dist = elig7.groupby("pin3").agg(district=("district", "first"), parcels=("matched", "size"), matched=("matched", "sum"))
dist["match_rate"] = (dist["matched"] / dist["parcels"]).round(3)
dist[["low_95", "high_95"]] = [tuple(round(x, 3) for x in wilson(int(r.matched), int(r.parcels))) for r in dist.itertuples()]
dist = dist.sort_values("parcels", ascending=False)
dist.to_csv(OUTPUTS / "district_match_rates.csv")
print("\nFeatured districts (7 days):")
print(dist.loc[[p for p in DISTRICTS if p in dist.index]])

# %% The hold-or-return rule, tested out of sample
model = DemandModel(orders, HISTORY_DAYS)
test = elig7[elig7["refusal_day"] - pd.Timedelta(days=HISTORY_DAYS) >= START].copy()
test["demand_per_day"] = [model.daily_demand(r.style, r.size, r.pin3, r.refusal_day) for r in test.itertuples()]
test["p_match"] = test["demand_per_day"].apply(lambda d: DemandModel.p_match(d, W))
test["exp_days_held"] = test["demand_per_day"].apply(lambda d: (1 - np.exp(-d * W)) / d if d > 0 else W)

bins = [-0.001, 0.02, 0.05, 0.10, 0.20, 0.40, 1.0]
test["p_bin"] = pd.cut(test["p_match"], bins)
calib = test.groupby("p_bin", observed=True).agg(parcels=("matched", "size"), predicted=("p_match", "mean"), actual=("matched", "mean")).round(3)
calib.to_csv(OUTPUTS / "rule_calibration.csv")
print("\nPredicted vs actual (should rise together):")
print(calib)


def policy_cost(df, hold_mask, batched):
    """Average cost per refused parcel. Held parcels: holding + (local re-delivery if matched, else batched return)."""
    h = df[hold_mask]
    held_cost = (HOLDING["per_parcel_per_day"] * h["exp_days_held"]
                 + np.where(h["matched"], COST["local_redelivery_from_lmdc"], batched)).sum()
    returned_cost = (~hold_mask).sum() * COST["individual_return"]
    return (held_cost + returned_cost) / len(df)


# Space at a hub is limited, so the rule's job is to pick WHICH parcels get a shelf slot.
# Compare: no holding (today), hold everything, and with limited space: random pick vs pick by P.
rng = np.random.default_rng(7)
pol = []
for batched_name, batched in (("batched Rs 50", COST["batched_return_low"]), ("batched Rs 120", COST["batched_return_high"])):
    options = [("Return all (today)", np.zeros(len(test), bool)), ("Hold all (unlimited space)", np.ones(len(test), bool))]
    for share in (0.5, 0.25):
        n_slots = int(share * len(test))
        rand = np.zeros(len(test), bool)
        rand[rng.choice(len(test), n_slots, replace=False)] = True
        top = np.zeros(len(test), bool)
        top[np.argsort(-test["p_match"].values)[:n_slots]] = True
        options += [(f"Space for {share:.0%}: random pick", rand), (f"Space for {share:.0%}: pick by rule", top)]
    for name, mask in options:
        pol.append({"batched_return": batched_name, "policy": name, "share_held": round(mask.mean(), 3),
                    "match_rate_of_held": round(test["matched"].values[mask].mean(), 3) if mask.any() else None,
                    "cost_per_refused_parcel": round(policy_cost(test, mask, batched), 1)})
pol = pd.DataFrame(pol)
pol.to_csv(OUTPUTS / "policy_comparison.csv", index=False)
with pd.option_context("display.width", 140):
    print("\n", pol)

# %% Does our formula reproduce the measured district rates?
cmp = (test.groupby("pin3").agg(district=("district", "first"), parcels=("matched", "size"),
                                measured=("matched", "mean"), modelled=("p_match", "mean"))
       .query("parcels >= 30").round(3).sort_values("parcels", ascending=False))
cmp.to_csv(OUTPUTS / "model_vs_measured.csv")
print("\nModel vs measured (districts with 30+ parcels):")
print(cmp)

# %% Charts for slides
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    piv = match_rates.pivot(index="area", columns="window_days", values="match_rate").loc[list(AREAS.values())]
    piv.plot(kind="bar", ax=ax, rot=0, color=["#c9b8f2", "#8f78ff", "#4b2fb8"])
    ax.set_ylabel("Share of returned parcels re-ordered nearby")
    ax.set_xlabel("")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(title="Days waiting", frameon=False)
    ax.set_title("How often a returned item's exact style + size is ordered again nearby\n(real Amazon India women's ethnic-wear orders, one seller, 2022)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUTS / "match_rate_by_area.png", dpi=200)

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 0.6], [0, 0.6], "--", color="#999", lw=1)
    ax.scatter(calib["predicted"], calib["actual"], s=calib["parcels"], color="#6242e8", alpha=0.8)
    ax.set_xlabel("Predicted chance of a match (rule)")
    ax.set_ylabel("Actual share matched")
    ax.set_title("Hold-or-return rule vs what really happened")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUTS / "rule_calibration.png", dpi=200)
    print("\ncharts saved in outputs/")
except ImportError:
    print("pip install matplotlib for charts")
