# %% [markdown]
# # Step 1.3 (optional) - Reddit posts about failed deliveries
# Uses Reddit's official API, which is free for personal research.
#
# Setup once (5 minutes):
# 1. Log in to Reddit, open https://www.reddit.com/prefs/apps, click "create another app", choose "script".
# 2. Copy the client id (under the app name) and the secret.
# 3. Set them as environment variables before running:
#      Windows (PowerShell):  $env:REDDIT_ID="..."; $env:REDDIT_SECRET="..."
#      Mac/Linux:             export REDDIT_ID=... REDDIT_SECRET=...
# 4. pip install praw
#
# Run: `python step1_collect/03_reddit_posts.py`

# %%
import os
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import RAW  # noqa: E402

try:
    import praw
except ImportError:
    sys.exit("Run: pip install praw")

QUERIES = ["meesho delivery", "meesho RTO", "valmo delivery", "fake delivery attempt",
           "delivery boy marked customer not available", "refused COD parcel"]
SUBREDDITS = "india+indiasocial+IndianFashionAddicts+IndiaShopping+Kanpur+lucknow"
LIMIT = 100  # per query

# %%
def main():
    cid, secret = os.getenv("REDDIT_ID"), os.getenv("REDDIT_SECRET")
    if not cid or not secret:
        sys.exit("Set REDDIT_ID and REDDIT_SECRET first (see top of file).")
    reddit = praw.Reddit(client_id=cid, client_secret=secret, user_agent="wapas-nahi-student-research/0.1")
    rows = []
    for q in QUERIES:
        for s in reddit.subreddit(SUBREDDITS).search(q, sort="relevance", time_filter="all", limit=LIMIT):
            rows.append({"query": q, "subreddit": str(s.subreddit), "id": s.id, "title": s.title,
                         "text": s.selftext[:2000], "score": s.score, "comments": s.num_comments,
                         "created_utc": s.created_utc, "url": f"https://reddit.com{s.permalink}"})
    df = pd.DataFrame(rows).drop_duplicates("id")
    df = df[df["title"].str.cat(df["text"], sep=" ").str.contains(r"deliver|parcel|courier|rto|cod", case=False, regex=True)]
    out = RAW / "reddit_posts.csv"
    df.to_csv(out, index=False)
    print(f"saved {len(df)} posts to {out}. Read them, and note useful ones in templates/review_notes.csv")


if __name__ == "__main__" or "__file__" not in globals():
    main()
