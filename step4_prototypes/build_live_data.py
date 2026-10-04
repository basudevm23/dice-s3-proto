# %% [markdown]
# # Build the data file for the live prototype app
# Packs everything the three live screens need into one file: app/data/live_data.json
#
# * every real order in each featured district (replayed in time order on the hub screen)
# * every real returned parcel there (each becomes a notification on the rider's phone at its real date)
# * the rule's chance of a nearby buyer for each parcel, using only the 30 days before it
# * rider reasons, fixes and success rates (from P1), and the 3-month projection (from P3)
#
# Run after p1_rider_screen.py and p3_savings_card.py:  python step4_prototypes/build_live_data.py

# %%
import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import PROCESSED, load_orders, load_json, save_json, DemandModel  # noqa: E402
from config import (COST, HOLDING, WINDOW_DAYS, REFUSAL_LAG_DAYS, HISTORY_DAYS, DISTRICTS,  # noqa: E402
                    HOLD_THRESHOLD, DEMO_SHELF_SLOTS, BLENDED_RTO, SOURCES)

APP_DATA = ROOT / "app" / "data"
APP_DATA.mkdir(parents=True, exist_ok=True)


def ref(order_id):
    return "P-" + hashlib.md5(str(order_id).encode()).hexdigest()[:5].upper()


# %%
def main():
    orders = load_orders()
    p1 = load_json(PROCESSED / "p1_rider_data.json")
    p3 = load_json(PROCESSED / "p3_savings.json")
    if not p1 or not p3:
        sys.exit("Run p1_rider_screen.py and p3_savings_card.py first.")
    start = orders["order_date"].min().normalize()
    model = DemandModel(orders, HISTORY_DAYS)
    live = orders[~orders["is_cancelled"]].copy()
    live["day"] = (live["order_date"] - start).dt.days

    districts = {}
    for pin3, name in DISTRICTS.items():
        d = live[live["pin3"] == pin3].sort_values(["day", "order_id"]).copy()
        if d.empty:
            continue
        # spread each day's orders evenly through the day so the feed flows
        d["rank"] = d.groupby("day").cumcount()
        d["n"] = d.groupby("day")["day"].transform("size")
        d["t"] = (d["day"] + (d["rank"] + 1) / (d["n"] + 1)).round(4)
        order_rows = d[["t", "style", "size", "category"]].values.tolist()

        r = orders[(orders["pin3"] == pin3) & orders["is_returned"]].copy()
        r["refusal_date"] = r["order_date"] + pd.Timedelta(days=REFUSAL_LAG_DAYS)
        r["t"] = ((r["refusal_date"] - start).dt.days + 0.45).round(4)   # refusals come in mid-morning
        returns = []
        for x in r.sort_values("t").itertuples():
            dem = model.daily_demand(x.style, x.size, pin3, x.refusal_date)
            p = DemandModel.p_match(dem, WINDOW_DAYS)
            returns.append({"id": ref(x.order_id), "t": x.t, "style": x.style, "size": x.size,
                            "category": x.category, "amount": None if pd.isna(x.amount) else round(float(x.amount)),
                            "pin": f"{x.pin[:3]}xxx", "demand_per_day": round(dem, 4), "p_match": round(p, 3)})
        districts[pin3] = {"name": name, "orders": order_rows, "returns": returns,
                           "projection": p3["districts"].get(pin3)}
        print(f"{name}: {len(order_rows)} real orders, {len(returns)} real returned parcels")

    out = {
        "meta": {"start_date": str(start.date()), "days": int(live["day"].max()) + 1, "sim_start_day": HISTORY_DAYS,
                 "window_days": WINDOW_DAYS, "hold_threshold": HOLD_THRESHOLD, "shelf_slots": DEMO_SHELF_SLOTS,
                 "blended_rto": BLENDED_RTO,
                 "costs": {"individual_return": COST["individual_return"], "local_redelivery": COST["local_redelivery_from_lmdc"],
                           "batched_low": COST["batched_return_low"], "batched_high": COST["batched_return_high"],
                           "exchange_forward": COST["exchange_forward_leg"], "holding_per_day": round(HOLDING["per_parcel_per_day"], 3)},
                 "sources": SOURCES},
        "reasons": p1["reasons"],
        "p3_assumptions": p3["assumptions"],
        "districts": districts,
    }
    save_json(out, APP_DATA / "live_data.json")
    print("\nNext: python app/server.py   then open http://localhost:5000")


if __name__ == "__main__" or "__file__" not in globals():
    main()
