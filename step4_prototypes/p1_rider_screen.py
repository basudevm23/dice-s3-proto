# %% [markdown]
# # P1 - Rider refusal screen (ladder steps 1-2)
# Builds the data the rider app mock-up uses: the reason list, the fix shown for each reason,
# its cost and its success rate - each with a source tag.
#
# Inputs : config.py (reasons, case-pack costs)
#          data/processed/survey_summary.json  (optional, from 05_survey_analysis.py)
# Output : data/processed/p1_rider_data.json
#
# Precedence: SURVEY (if USE_SURVEY and enough answers) > INDUSTRY/DECK > shown as unknown.

# %%
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import PROCESSED, load_json, save_json  # noqa: E402
from config import REASON_CODES, REASON_GROUPS, INDUSTRY_NDR_RECOVERY, USE_SURVEY  # noqa: E402

MIN_N = 30
survey = load_json(PROCESSED / "survey_summary.json", {}) if USE_SURVEY else {}


# %% Group shares (how often each kind of failure happens)
def group_shares():
    return {g["id"]: (g["deck"], "DECK (published range " + f"{g['low']:.0%}-{g['high']:.0%})") for g in REASON_GROUPS}


# %% Split inside each group (e.g. how refusals divide into no cash / changed mind / fit)
def code_shares(groups):
    mix = survey.get("reason_mix", {})
    have_survey = survey.get("had_failed_delivery_n", 0) >= MIN_N
    out = {}
    for gid, (gshare, gsrc) in groups.items():
        members = [r for r in REASON_CODES if r["group"] == gid]
        if have_survey:
            w = {r["id"]: mix.get(r["id"], {}).get("share", 0) for r in members}
            tot = sum(w.values())
        if have_survey and tot > 0:
            for r in members:
                out[r["id"]] = (gshare * w[r["id"]] / tot, f"{gsrc}; split from SURVEY")
        else:
            for r in members:
                out[r["id"]] = (gshare / len(members), f"{gsrc}; even split (ASSUMPTION until survey)")
    return out


# %% Fix success
def success(code):
    if code["success_default"] is not None:
        return code["success_default"], "no fix at the door"
    q = (survey.get("fix_rates") or {}).get(code["id"])
    if q and q.get("n", 0) >= MIN_N:
        return q["rate"], f"SURVEY (n={q['n']}, 75/25 intent rule)"
    lo, hi = INDUSTRY_NDR_RECOVERY
    return (lo + hi) / 2, f"INDUSTRY {lo:.0%}-{hi:.0%} of failed deliveries recoverable (no survey yet)"


# %%
def main():
    groups = group_shares()
    shares = code_shares(groups)
    reasons = []
    for c in REASON_CODES:
        s, s_src = success(c)
        share, share_src = shares[c["id"]]
        reasons.append({"id": c["id"], "group": c["group"], "label": c["label"], "fix": c["fix"],
                        "fix_cost": c["fix_cost"], "fix_cost_source": c["cost_source"],
                        "success_rate": round(s, 3), "success_source": s_src,
                        "share_of_refusals": round(share, 3), "share_source": share_src,
                        "if_fix_fails": "Parcel goes to the hub shelf (P2)"})
    rescued = sum(r["share_of_refusals"] * r["success_rate"] for r in reasons if r["id"] != "fit_quality")
    exchanged = sum(r["share_of_refusals"] * r["success_rate"] for r in reasons if r["id"] == "fit_quality")
    out = {"reasons": reasons,
           "expected_delivered_after_door_fix": round(rescued, 3),
           "expected_exchanges": round(exchanged, 3),
           "note": "Exchanges save the customer's order, but the refused unit still goes to the hub shelf."}
    save_json(out, PROCESSED / "p1_rider_data.json")
    for r in reasons:
        print(f"{r['label']:<36} share {r['share_of_refusals']:.1%}  fix works {r['success_rate']:.0%}  [{r['success_source'][:30]}]")
    print(f"\nDelivered after a door fix: {rescued:.1%} of refused parcels; exchanges: {exchanged:.1%}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
