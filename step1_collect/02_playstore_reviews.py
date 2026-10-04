# %% [markdown]
# # Step 1.2 - Customer and rider voices from Google Play reviews
# Public app reviews are a free source of *why* deliveries fail, in customers' own words.
#
# What this does
# 1. Finds the app IDs (Meesho shopping app, Valmo partner apps) via Play Store search.
# 2. Downloads recent public reviews (English + Hindi).
# 3. Keeps only delivery-related reviews and tags each with our reason codes.
# 4. Writes a 100-review sample for you to hand-check, so you can report how accurate the tagging is.
#
# Fair use: reviews are public, but collect gently (counts below are modest), use them for research only,
# and never publish reviewer names. Quote paraphrased, not verbatim, in the deck.
#
# Install once: `pip install google-play-scraper`
# Run: `python step1_collect/02_playstore_reviews.py`

# %%
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import RAW, PROCESSED  # noqa: E402

try:
    from google_play_scraper import Sort, reviews, search
except ImportError:
    sys.exit("Run: pip install google-play-scraper")

# %% 1. Which apps?
SEARCH_TERMS = ["Meesho", "Valmo", "Valmo delivery partner"]
KNOWN_APPS = {"com.meesho.supply": "Meesho (shopping)"}  # add more after checking the search printout

def list_candidates():
    for term in SEARCH_TERMS:
        try:
            hits = search(term, lang="en", country="in", n_hits=5)
        except Exception as e:  # network / layout changes
            print(f"search failed for {term}: {e}")
            continue
        print(f"\nSearch '{term}':")
        for h in hits:
            print(f"   {h.get('appId')}  |  {h.get('title')}  |  {h.get('developer')}")

# %% 2. Download reviews
REVIEWS_PER_LANG = 3000   # per app per language; raise slowly if you need more

def fetch(app_id, lang):
    out, token = [], None
    while len(out) < REVIEWS_PER_LANG:
        batch, token = reviews(app_id, lang=lang, country="in", sort=Sort.NEWEST,
                               count=min(200, REVIEWS_PER_LANG - len(out)), continuation_token=token)
        out.extend(batch)
        if not token or not batch:
            break
        time.sleep(1.0)  # be polite
    df = pd.DataFrame(out)
    if df.empty:
        return df
    df["app_id"], df["lang"] = app_id, lang
    return df[["app_id", "lang", "reviewId", "content", "score", "at", "thumbsUpCount"]]

# %% 3. Tag delivery reasons (English + Hinglish keywords)
TAGS = {
    "fake_attempt":  r"(fake|false).{0,15}(attempt|delivery)|never came|didn'?t come|did not come|no call|without call|nahi aaya|aaya hi nahi|call nahi|bina call",
    "not_home":      r"not (at )?home|not available|wasn'?t home|ghar (pe|par) nahi|unavailable",
    "no_cash":       r"no cash|cash (nahi|not)|change nahi|didn'?t have (cash|money)|paise nahi|upi",
    "address":       r"address|location|landmark|pin ?code|pata",
    "delay":         r"late|delay|days? (late|delay)|weeks?|der se|bahut (din|time)",
    "fit_quality":   r"size|fit|quality|different product|wrong (item|product)|not as (shown|described)",
    "rto_return":    r"\brto\b|returned to (seller|origin)|cancel(l)?ed (by|automatically)|wapas (chala|bhej)",
    "rider_behaviour": r"rude|misbehav|asked (for )?(extra|money)|delivery boy|rider",
}
DELIVERY_FILTER = r"deliver|courier|parcel|rider|delivery boy|order (not|never)|rto|return|cancel|valmo"

def tag(text):
    t = str(text).lower()
    return [k for k, rx in TAGS.items() if re.search(rx, t)]

# %%
def main():
    list_candidates()
    frames = []
    for app_id, name in KNOWN_APPS.items():
        for lang in ("en", "hi"):
            print(f"fetching {name} [{lang}] ...")
            try:
                frames.append(fetch(app_id, lang))
            except Exception as e:
                print(f"  failed: {e}")
    raw = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
    if raw.empty:
        sys.exit("No reviews downloaded. Check your internet connection or the app IDs.")
    raw.to_csv(RAW / "playstore_reviews_raw.csv", index=False)

    d = raw[raw["content"].str.contains(DELIVERY_FILTER, case=False, na=False, regex=True)].copy()
    d["tags"] = d["content"].apply(tag)
    d = d[d["tags"].str.len() > 0]
    d.to_csv(PROCESSED / "playstore_delivery_reviews.csv", index=False)

    counts = d.explode("tags")["tags"].value_counts()
    summary = pd.DataFrame({"reviews": counts, "share_of_delivery_reviews": (counts / len(d)).round(3)})
    summary.to_csv(PROCESSED / "playstore_reason_counts.csv")
    print(f"\n{len(raw)} reviews downloaded, {len(d)} about deliveries with a tag.\n")
    print(summary)

    # Hand-check sample: fill the 'correct_tag' column yourself, then report precision.
    sample = d.sample(min(100, len(d)), random_state=1)[["reviewId", "content", "tags"]].copy()
    sample["correct_tag"] = ""
    sample.to_csv(PROCESSED / "playstore_handcheck_sample.csv", index=False)
    print("\nOpen data/processed/playstore_handcheck_sample.csv and fill 'correct_tag' for each row.")


if __name__ == "__main__" or "__file__" not in globals():
    main()
