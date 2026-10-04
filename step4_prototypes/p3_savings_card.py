# %% [markdown]
# # P3 - Savings card (ladder step 5 + the business case)
# For each featured district, starting from the district's REAL order count in the dataset:
#   refused parcels (at Valmo's 17% RTO) -> fixed at the door -> held -> resold locally -> batched return
# and the cost per refused parcel vs Rs 120 today.
#
# Inputs : orders_clean.csv, outputs/district_match_rates.csv (from step 3),
#          p1_rider_data.json (from P1), survey_summary.json (optional)
# Output : data/processed/p3_savings.json
#
# Two honest ranges are always shown:
#   * batched return cost Rs 50 (moves like forward freight) to Rs 120 (moves alone)
#   * k = how much more demand Valmo sees for the identical item than this one brand (k=1 is measured)

# %%
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import PROCESSED, OUTPUTS, load_orders, load_json, save_json, DemandModel, scale_match  # noqa: E402
from config import (BLENDED_RTO, COST, HOLDING, WINDOW_DAYS, REFUSAL_LAG_DAYS, HISTORY_DAYS,  # noqa: E402
                    DISTRICTS, DEFAULT_K, USE_SURVEY)

MIN_PARCELS_FOR_MEASURED = 30


def modelled_match_rate(pin3, orders, model):
    """Average chance of a match if any of the district's orders had been refused (our formula, k=1)."""
    live = orders[(~orders["is_cancelled"]) & (orders["pin3"] == pin3)]
    start, end = orders["order_date"].min(), orders["order_date"].max()
    days = live["order_date"] + pd.Timedelta(days=REFUSAL_LAG_DAYS)
    ok = (days - pd.Timedelta(days=HISTORY_DAYS) >= start) & (days + pd.Timedelta(days=WINDOW_DAYS) <= end)
    ps = [DemandModel.p_match(model.daily_demand(r.style, r.size, pin3, d), WINDOW_DAYS)
          for r, d in zip(live[ok].itertuples(), days[ok])]
    return float(np.mean(ps)) if ps else 0.0


def ladder(refused, door, match_rate, acceptance, batched):
    delivered_at_door = refused * door["delivered"]
    to_shelf = refused - delivered_at_door                 # includes exchanged units
    resold = to_shelf * match_rate * acceptance
    batched_back = to_shelf - resold
    cost = (refused * door["cost_per_refusal"]
            + resold * (COST["local_redelivery_from_lmdc"] + HOLDING["per_parcel_per_day"] * WINDOW_DAYS / 2)
            + batched_back * (batched + HOLDING["per_parcel_per_day"] * WINDOW_DAYS))
    return {"refused": refused, "fixed_at_door": delivered_at_door, "orders_saved_by_exchange": refused * door["exchanged"],
            "sent_to_shelf": to_shelf, "resold_locally": resold, "batched_return": batched_back,
            "cost_today": refused * COST["individual_return"], "cost_with_wapas_nahi": cost,
            "cost_per_refused_today": COST["individual_return"], "cost_per_refused_new": cost / refused if refused else 0}


# %%
def main():
    orders = load_orders()
    model = DemandModel(orders, HISTORY_DAYS)
    p1 = load_json(PROCESSED / "p1_rider_data.json")
    if not p1:
        sys.exit("Run step4_prototypes/p1_rider_screen.py first.")
    survey = load_json(PROCESSED / "survey_summary.json", {}) if USE_SURVEY else {}
    measured = pd.read_csv(OUTPUTS / "district_match_rates.csv", dtype={"pin3": str}).set_index("pin3")

    fix_cost = sum(r["share_of_refusals"] * r["success_rate"] * r["fix_cost"] for r in p1["reasons"])
    door = {"delivered": p1["expected_delivered_after_door_fix"], "exchanged": p1["expected_exchanges"],
            "cost_per_refusal": fix_cost}
    acc = survey.get("buyer_acceptance", {})
    acceptance, acc_src = (acc["accept"], f"SURVEY (n={acc['n']})") if acc.get("n", 0) >= 30 else (1.0, "not yet measured (survey D1)")

    days_span = (orders["order_date"].max() - orders["order_date"].min()).days + 1
    out = {"assumptions": {"rto": BLENDED_RTO, "rto_source": "CASE_PACK (80% COD x 20% + 20% prepaid x 5%)",
                           "door_fix": door, "door_fix_source": "P1 (survey if available, else industry range)",
                           "buyer_acceptance": acceptance, "buyer_acceptance_source": acc_src,
                           "window_days": WINDOW_DAYS, "k_values": DEFAULT_K,
                           "batched_return_range": [COST["batched_return_low"], COST["batched_return_high"]]},
           "districts": {}}
    for pin3, name in DISTRICTS.items():
        live_n = int(((~orders["is_cancelled"]) & (orders["pin3"] == pin3)).sum())
        refused = live_n * BLENDED_RTO
        if pin3 in measured.index and measured.loc[pin3, "parcels"] >= MIN_PARCELS_FOR_MEASURED:
            base, src = float(measured.loc[pin3, "match_rate"]), f"MEASURED ({int(measured.loc[pin3, 'parcels'])} real parcels)"
        else:
            base, src = modelled_match_rate(pin3, orders, model), "MODELLED from the district's real order history (too few returns to measure)"
        scen = {}
        for k in DEFAULT_K:
            m = scale_match(base, k)
            for label, batched in (("low", COST["batched_return_low"]), ("high", COST["batched_return_high"])):
                res = ladder(refused, door, m, acceptance, batched)
                scen[f"k{k}_{label}"] = {kk: round(v, 1) for kk, v in res.items()} | {"match_rate": round(m, 3)}
        out["districts"][pin3] = {"district": name, "real_orders_in_dataset": live_n, "period_days": days_span,
                                  "refused_at_valmo_rto": round(refused), "match_rate_k1": round(base, 3),
                                  "match_rate_source": src, "scenarios": scen}
        s1, s5 = scen["k1_low"], scen["k5_low"]
        print(f"{name}: {live_n} real orders -> {refused:.0f} refused at 17%. Match {base:.1%} [{src.split(' ')[0]}]. "
              f"Cost per refused parcel Rs 120 -> Rs {s1['cost_per_refused_new']:.0f} (k=1) / Rs {s5['cost_per_refused_new']:.0f} (k=5), "
              f"batched at Rs 50; Rs {scen['k1_high']['cost_per_refused_new']:.0f} if batched costs Rs 120")
    save_json(out, PROCESSED / "p3_savings.json")


if __name__ == "__main__" or "__file__" not in globals():
    main()
