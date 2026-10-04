# %% [markdown]
# # P2 - Hub shelf: hold or return? (ladder steps 3-4)
# Builds a replay of REAL orders for each featured district:
# * every real returned parcel in the district, with the rule's chance of a match, its decision,
#   and what actually happened in the next 7 days;
# * one "featured parcel" for the demo, plus the real order stream it waits through.
#
# Inputs : data/processed/orders_clean.csv
# Output : data/processed/p2_hub_scenarios.json
#
# Run for other districts:  python step4_prototypes/p2_hub_shelf.py 226 208 110

# %%
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import PROCESSED, load_orders, save_json, DemandModel, scale_match  # noqa: E402
from config import (COST, HOLDING, WINDOW_DAYS, REFUSAL_LAG_DAYS, HISTORY_DAYS, DISTRICTS,  # noqa: E402
                    DEFAULT_K, RETURNED_STATUSES, HOLD_THRESHOLD)



def hold_gain(p, days_held):
    """Expected Rs saved by holding vs returning straight away at Rs 120 (batched return at the low end)."""
    matched_saving = p * (COST["individual_return"] - COST["local_redelivery_from_lmdc"])
    batched_saving = (1 - p) * (COST["individual_return"] - COST["batched_return_low"])
    return matched_saving + batched_saving - HOLDING["per_parcel_per_day"] * days_held


# %%
def build(pin3, orders, model, live, end):
    d_orders = live[live["pin3"] == pin3]
    parcels = orders[(orders["pin3"] == pin3) & orders["status"].isin(RETURNED_STATUSES)].copy()
    parcels["refusal_day"] = parcels["order_date"] + pd.Timedelta(days=REFUSAL_LAG_DAYS)
    parcels = parcels[(parcels["refusal_day"] - pd.Timedelta(days=HISTORY_DAYS) >= orders["order_date"].min())
                      & (parcels["refusal_day"] + pd.Timedelta(days=WINDOW_DAYS) <= end)]
    used, rows = set(), []
    for p in parcels.sort_values("refusal_day").itertuples():
        dem = model.daily_demand(p.style, p.size, pin3, p.refusal_day)
        pm = DemandModel.p_match(dem, WINDOW_DAYS)
        days_held = (1 - np.exp(-dem * WINDOW_DAYS)) / dem if dem > 0 else WINDOW_DAYS
        lo, hi = p.refusal_day, p.refusal_day + pd.Timedelta(days=WINDOW_DAYS)
        cand = d_orders[(d_orders["sku"] == p.sku) & (d_orders["order_date"] > lo) & (d_orders["order_date"] <= hi)
                        & (d_orders["order_id"] != p.order_id)].sort_values("order_date")
        cand = cand[~cand.index.isin(used)]
        match_day = None
        if len(cand):
            used.add(cand.index[0])
            match_day = int((cand["order_date"].iloc[0] - p.refusal_day).days)
        rows.append({"order_ref": "P-" + hashlib.md5(str(p.order_id).encode()).hexdigest()[:5].upper(),   # anonymised
                     "category": p.category, "style": p.style, "size": p.size,
                     "refusal_day": str(p.refusal_day.date()), "demand_per_day": round(dem, 3),
                     "p_match": round(pm, 3), "p_match_k": {str(k): round(scale_match(pm, k), 3) for k in DEFAULT_K},
                     "expected_gain_rs": round(hold_gain(pm, days_held), 1),
                     "decision": "HOLD" if pm >= HOLD_THRESHOLD else "RETURN",
                     "actually_matched": match_day is not None, "match_after_days": match_day})
    res = pd.DataFrame(rows)
    if res.empty:
        return None

    # Featured parcel: a HOLD that really matched, with a middling (believable) chance; else the highest-P parcel
    hits = res[(res["decision"] == "HOLD") & res["actually_matched"]]
    if len(hits):
        feat = hits.iloc[(hits["p_match"] - 0.5).abs().argsort().iloc[0]]
    else:
        feat = res.sort_values("p_match", ascending=False).iloc[0]
    f_day = pd.Timestamp(feat["refusal_day"])
    stream = d_orders[(d_orders["order_date"] > f_day) & (d_orders["order_date"] <= f_day + pd.Timedelta(days=WINDOW_DAYS))]
    same_style = stream["style"] == feat["style"]
    same_sku = same_style & (stream["size"] == feat["size"])
    stream_out = (stream.assign(day=(stream["order_date"] - f_day).dt.days, is_match=same_sku, same_style=same_style)
                  [["day", "category", "style", "size", "is_match", "same_style"]]
                  .sort_values(["day", "is_match"], ascending=[True, False]))

    days_span = (live["order_date"].max() - live["order_date"].min()).days + 1
    return {
        "pin3": pin3, "district": DISTRICTS.get(pin3, pin3),
        "real_orders_in_dataset": int(len(d_orders)), "orders_per_day": round(len(d_orders) / days_span, 1),
        "returned_parcels_tested": int(len(res)),
        "held": int((res["decision"] == "HOLD").sum()),
        "held_and_matched": int(((res["decision"] == "HOLD") & res["actually_matched"]).sum()),
        "returned_but_would_have_matched": int(((res["decision"] == "RETURN") & res["actually_matched"]).sum()),
        "match_rate_all_parcels": round(res["actually_matched"].mean(), 3),
        "match_rate_of_held": round(res.loc[res["decision"] == "HOLD", "actually_matched"].mean(), 3)
        if (res["decision"] == "HOLD").any() else None,
        "parcels": res.to_dict("records"),
        "featured_parcel": feat.to_dict(),
        "featured_order_stream": stream_out.to_dict("records"),
        "featured_stream_summary": {"orders_in_window": int(len(stream_out)),
                                    "same_style": int(stream_out["same_style"].sum()),
                                    "exact_match": int(stream_out["is_match"].sum())},
    }


# %%
def main(pins):
    orders = load_orders()
    live = orders[~orders["is_cancelled"]]
    model = DemandModel(orders, HISTORY_DAYS)
    out = {"window_days": WINDOW_DAYS, "hold_threshold": HOLD_THRESHOLD,
           "costs": {"individual_return": COST["individual_return"], "local_redelivery": COST["local_redelivery_from_lmdc"],
                     "batched_return_range": [COST["batched_return_low"], COST["batched_return_high"]],
                     "holding_per_day": round(HOLDING["per_parcel_per_day"], 2)},
           "districts": {}}
    for pin3 in pins:
        res = build(pin3, orders, model, live, orders["order_date"].max())
        if res is None:
            print(f"{pin3}: no testable returned parcels")
            continue
        out["districts"][pin3] = res
        f = res["featured_parcel"]
        print(f"{res['district']} ({pin3}): {res['returned_parcels_tested']} real returned parcels, "
              f"held {res['held']}, of which matched {res['held_and_matched']}; "
              f"featured {f['category']} size {f['size']} P={f['p_match']:.0%} -> {f['decision']}, "
              f"matched after {f['match_after_days']} days")
    save_json(out, PROCESSED / "p2_hub_scenarios.json")


if __name__ == "__main__" or "__file__" not in globals():
    args = [a for a in sys.argv[1:] if a.isdigit()] if "__file__" in globals() else []
    main(args or list(DISTRICTS))
