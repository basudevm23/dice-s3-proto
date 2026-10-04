# %% [markdown]
# # Step 2.2 - Customer survey -> model inputs
# Input : data/raw/survey_responses.csv  (Google Forms -> Sheets -> Download CSV)
# Output: data/processed/survey_summary.json  (read by P1 and P3)
#
# What it computes
# * Reason mix (B3), mapped to our reason codes, with 95% ranges.
# * Fix success rates (C1-C5) using the stated-intent rule: 75% of "Definitely yes" + 25% of "Probably yes".
# * Buyer acceptance of a resold sealed parcel (D1).
# Main result = COD-heavy respondents (A5). If fewer than 30 of them, all respondents are used and flagged.

# %%
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import RAW, PROCESSED, wilson, save_json  # noqa: E402
from config import INTENT_WEIGHTS  # noqa: E402

MIN_SEGMENT = 30
B3_TO_CODE = {
    "I did not have cash at that moment": "no_cash",
    "I changed my mind or found it cheaper elsewhere": "changed_mind",
    "It took too long and I did not need it any more": "changed_mind",      # lateness -> refusal; reported separately too
    "Someone in my family did not want me to take it": "changed_mind",
    "The size or item did not look right": "fit_quality",
    "I was not home or could not take the call": "not_home",
    "I asked them to come another day, but it went back": "reschedule",
    "The delivery person could not find my address": "address",
    "The delivery person never actually came, but it was marked as attempted": "carrier",  # fake attempt = our side
    "I did not place that order": "fake",
}
C_TO_CODE = {"C1": "no_cash", "C2": "reschedule", "C3": "not_home", "C4": "address", "C5": "fit_quality"}


def col(df, code):
    hits = [c for c in df.columns if c.strip().startswith(code + ".")]
    if not hits:
        raise KeyError(f"No column starting with '{code}.' - did the question titles change?")
    return hits[0]


def intent_rate(series):
    s = series.dropna()
    if s.empty:
        return None
    rate = s.map(INTENT_WEIGHTS).fillna(0).mean()
    yes = s.isin(["Definitely yes", "Probably yes"]).mean()
    lo, hi = wilson(round(rate * len(s)), len(s))
    return {"rate": round(rate, 3), "said_yes": round(yes, 3), "range": [round(lo, 3), round(hi, 3)], "n": int(len(s))}


# %%
def main():
    path = RAW / "survey_responses.csv"
    if not path.exists():
        sys.exit(f"Put the exported Google Form CSV at {path} and run again.")
    df = pd.read_csv(path)
    n_all = len(df)
    cod = df[df[col(df, "A5")].eq("Almost always cash on delivery (COD)")]
    seg, seg_name = (cod, "COD users") if len(cod) >= MIN_SEGMENT else (df, "all respondents (too few COD users)")
    print(f"{n_all} responses, {len(cod)} COD users -> using {seg_name}")

    # Reason mix (B3) among people who had a failed delivery
    b3 = seg[col(seg, "B3")].dropna()
    codes = b3.map(B3_TO_CODE).fillna("other")
    reason_mix = {}
    for code, k in codes.value_counts().items():
        lo, hi = wilson(k, len(codes))
        reason_mix[code] = {"share": round(k / len(codes), 3), "range": [round(lo, 3), round(hi, 3)], "n": int(k)}
    late = (b3 == "It took too long and I did not need it any more").mean() if len(b3) else 0
    fake_attempt = (b3 == "The delivery person never actually came, but it was marked as attempted").mean() if len(b3) else 0

    fix_rates = {code: intent_rate(seg[col(seg, q)]) for q, code in C_TO_CODE.items()}

    d1 = seg[col(seg, "D1")].dropna()
    accept = d1.isin(["Yes, no problem", "Yes, if it is sealed and has passed a check"])
    lo, hi = wilson(int(accept.sum()), len(d1))
    acceptance = {"accept": round(accept.mean(), 3), "range": [round(lo, 3), round(hi, 3)],
                  "with_discount_only": round(d1.eq("Only if I got a small discount").mean(), 3), "n": int(len(d1))}

    pin3 = df[col(df, "E3")].dropna().astype(str).str.zfill(3).value_counts().head(10).to_dict() if any(
        c.startswith("E3.") for c in df.columns) else {}

    out = {"responses": n_all, "segment": seg_name, "segment_n": int(len(seg)),
           "had_failed_delivery_n": int(len(b3)), "reason_mix": reason_mix,
           "share_refused_because_late": round(late, 3),
           "share_fake_attempt_reported": round(fake_attempt, 3), "fix_rates": fix_rates,
           "buyer_acceptance": acceptance, "top_pin3": pin3,
           "note": "Stated intent, adjusted 75/25. Friends-and-family sample: treat as directional."}
    save_json(out, PROCESSED / "survey_summary.json")
    print(pd.DataFrame(reason_mix).T)
    print(pd.DataFrame({k: v for k, v in fix_rates.items() if v}).T)
    print("acceptance:", acceptance)
    if len(b3) < 100:
        print(f"\nOnly {len(b3)} people reported a failed delivery: reason shares are rough (aim for 100+).")


if __name__ == "__main__" or "__file__" not in globals():
    main()
