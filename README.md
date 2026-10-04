# Wapas Nahi: data pipeline + live prototype

There are two parts in this folder:

1. **The data pipeline** (`step1_…` to `step4_…`). It downloads the real order data, tests the idea, and builds the data file the prototype uses.
2. **The live prototype** (`app/`). It has three linked screens, all reading one shared simulation:
   - **P1 · Rider app** (for riders, on their phone): an alert arrives, the rider picks what happened and gets one clear instruction. English and Hindi.
   - **P2 · Hub app** (for hub staff, on a tablet): "Do now" task cards (put on shelf A3, take out A3 for a nearby order, move to the return bag, send back), a labelled shelf rack, and a Done button for each task. English and Hindi.
   - **P3 · Manager dashboard** (for Valmo managers, on a laptop): money saved so far, what happened to refused parcels, and a 3-month estimate.

   Whatever you tap on the rider phone appears on the hub and savings screens within a second, on any device that has the link open.

The app already contains a built data file (`app/data/live_data.json`), so you can run the prototype straight away (Part B) and do the data steps afterwards.

---

## Folder map

```
wapas-nahi/
├── README.md
├── requirements.txt            pipeline packages
├── config.py                   every number, tagged with its source
├── common.py                   shared helpers
├── run_all.py                  runs the whole pipeline
├── step1_collect/              01 get data · 02 Play Store reviews (optional) · 03 Reddit (optional)
├── step2_prepare/              04 clean orders · 05 survey analysis
├── step3_analysis/             07 back-test: match rates, rule test, charts for slides
├── step4_prototypes/           p1 · p2 · p3 data builders + build_live_data.py (feeds the app)
├── google_form/                create_forms.gs (customer survey) + FORM_CONTENT.md
├── data/raw/                   downloads + survey CSV (you add this)
├── data/processed/             cleaned data, prototype JSON
├── outputs/                    tables and charts for slides
├── app/                        the live prototype
│   ├── server.py               web server (Flask)
│   ├── sim.py                  the shared live simulation
│   ├── data/live_data.json     built by step4_prototypes/build_live_data.py
│   ├── static/                 rider.html · hub.html · savings.html · present.html · index.html
│   └── requirements.txt
├── render.yaml                 one-click hosting on Render
└── .gitignore
```

---

## Part A: set up and run the data pipeline

### A1. One-time setup

You need Python 3.10 or newer. Check with `python --version`; on Mac, use `python3` in place of `python` everywhere below. Open a terminal **inside the unzipped `wapas-nahi` folder**:

- **Windows:** open the folder in File Explorer, click the address bar, type `cmd`, and press Enter.
- **Mac:** right-click the folder and choose "New Terminal at Folder".

```
python -m venv .venv
.venv\Scripts\activate                 (Windows)
source .venv/bin/activate              (Mac/Linux)
pip install -r requirements.txt
pip install -r app/requirements.txt
```

You'll see `(.venv)` at the start of the prompt. Run the `activate` line again every time you open a new terminal.

### A2. Run everything

```
python run_all.py
```

| Step | What happens | What you should see |
|---|---|---|
| 01_get_data | downloads the Amazon India order file and the India Post pincode directory into `data/raw/` | `saved …amazon_sale_report.csv` |
| 04_prepare_orders | cleans orders, adds district names | Kanpur 470 orders, Lucknow 1,397, Bengaluru 11,581 |
| 05_survey_analysis | reads your survey CSV if it exists | "(stopped: Put the exported Google Form CSV…)" if not, which is fine |
| 07_backtest | measures how often a returned item is re-ordered nearby | same PIN district, 7 days ≈ 13.6%; charts in `outputs/` |
| p1 / p2 / p3 | builds rider, hub and savings data | district summaries |
| build_live_data | refreshes `app/data/live_data.json` | "Next: python app/server.py" |

It takes about 2–3 minutes. The two charts for your slides are in `outputs/`.

### A3. Add your survey answers (optional)

1. Open the form, go to Responses → green Sheets icon → File → Download → CSV.
2. Rename the file to `survey_responses.csv` and put it in `data/raw/`.
3. Run `python run_all.py` again.

The survey is supporting evidence only. It is used for door-fix rates and buyer acceptance once **30 or more** people have answered, and otherwise industry ranges are used. To ignore it completely, set `USE_SURVEY = False` in `config.py`.

### A4. Optional extra evidence

- **Play Store reviews:** run `python step1_collect/02_playstore_reviews.py`. It writes delivery complaints tagged by reason to `data/processed/`. Use it for quotes and themes, not for model numbers.
- **Reddit:** `03_reddit_posts.py` needs free API keys; the instructions are at the top of that file.

---

## Part B: run the live prototype on your laptop

```
python app/server.py
```

Then open these in your browser:

| Address | What it shows |
|---|---|
| http://localhost:5000 | start page, with links and a QR code |
| **http://localhost:5000/present** | **all three screens side by side**: best for presenting |
| http://localhost:5000/rider | P1 Rider app. Opened on its own, it also shows a "Demo: next parcel" button |
| http://localhost:5000/hub | P2 Hub app. Opened on its own, it also shows the control bar |
| http://localhost:5000/savings | P3 Manager dashboard |

Stop the server with `Ctrl + C`.

**Using your real phone as the rider phone on the same Wi-Fi:**

1. Find your laptop's address. On Windows run `ipconfig` and look for the IPv4 address (e.g. `192.168.1.7`); on Mac look in System Settings → Wi-Fi → Details.
2. On your phone, open `http://192.168.1.7:5000/rider`.
3. If it doesn't load on Windows, allow Python through the firewall when Windows asks.

### Controls (top bar of the hub and presenter pages)

| Control | What it does |
|---|---|
| District | Lucknow (default), Kanpur or Bengaluru. Switching restarts that district. |
| Pause / Play | stops or starts the clock |
| Speed | Fast (6 s per day), Normal (20 s), Slow (60 s) |
| Shelf | 10, 40 or 100 slots. Set it to 10 to show the app choosing which parcels keep a slot when space is short. |
| **Next refused parcel now** | brings the next real refused parcel to the rider's phone immediately. Use this while presenting so you don't have to wait. |
| Auto-rider | if nobody answers the phone within 25 seconds, it answers automatically (picks a reason by the real mix and whether the fix worked by its success rate). Turn it **off** when you want to tap everything yourself. |
| हिंदी / English (on the rider and hub apps) | switches that app's language |
| ✓ Done (on hub task cards) | marks the task done; the next waiting task takes its place |
| Reset | starts the district again |

### What is real and what is a setting

| On screen | Source |
|---|---|
| Dates, orders arriving, which parcels get refused, their item / size / COD amount | **real**: Amazon India order data, replayed on their real dates |
| The chance shown on each parcel | the rule, using only the 30 days of real orders before that day |
| A shelf match | a real later order for the same style and size in the same district |
| ₹120 return, ₹21 local delivery, ₹50 forward | case pack |
| Batched return ₹50–₹120 | range between two case-pack figures |
| Reason mix, fix success | deck shares + industry 40–50% (or your survey, if 30+ answers) |
| Chance shown as High / Medium / Low | High at 30% or more, Medium 10–30%, Low below 10% |
| Buyer accepts a resold parcel | 81% from your survey (question D1) |
| 40 shelf slots, 5% hold threshold | **demo settings** in `config.py` |
| 3-month estimate | one seller's real orders in the district × 17% RTO. The rupee total is for that volume; the per-parcel saving is what scales to Valmo |

---

## Part C: make a public link

### Option 1 (quickest): a temporary link from your laptop

This works while your laptop and the server are running. It needs no account and is free.

1. Install cloudflared:
   - Windows: `winget install --id Cloudflare.cloudflared`
   - Mac: `brew install cloudflared`
2. Start the app in one terminal: `python app/server.py`
3. In a **second** terminal, run: `cloudflared tunnel --url http://localhost:5000`
4. It prints a link like `https://random-words.trycloudflare.com`. That's your public link: `/present`, `/rider` and so on all work on it.

The link changes each time you restart cloudflared, so start it shortly before the meeting.

### Option 2 (permanent): host it on Render (free)

1. Create a GitHub account and a **new repository** (it can be public or private).
2. Upload this whole folder. Either drag and drop it on github.com with "Add file → Upload files", or use GitHub Desktop. The `.gitignore` already leaves out the large raw CSVs and `.venv`. Make sure `app/data/live_data.json` **is** uploaded.
3. Go to render.com, sign in with GitHub, choose **New → Blueprint**, and pick your repository. Render reads `render.yaml` and sets everything up.
4. After 2–3 minutes you get a permanent link like `https://wapas-nahi.onrender.com`. Put `https://wapas-nahi.onrender.com/present` in your deck.

Things to know about the free plan:

- After 15 minutes with no visitors, the site sleeps. The first visit then takes about a minute to wake it, so **open the link a few minutes before you present.**
- Everyone who opens the link sees **the same live demo**. That's what makes it real-time, but anyone can press Reset. Press Reset yourself just before you start.
- If you re-run the pipeline, upload the new `app/data/live_data.json` to GitHub, and Render redeploys automatically.

---

## Part D: a 2-minute demo script

1. Open `/present`. In the top bar choose **Bengaluru**, untick **Auto-rider**, set **Normal** speed, and press **Reset**.
2. **Rider, a fix that works.** Click **Next refused parcel now**. On the phone, tap the alert, choose **No cash right now**. The app says "Ask the customer to pay by UPI". Tap **✓ Customer agreed**: *"Delivered, no return trip."*
3. **Rider, a parcel that comes back.** Click **Next refused parcel now** again, choose **Doesn't want it any more**, then **OK, bringing it back**. *"The rider just keeps it sealed and brings it back."*
4. **Hub.** The parcel appears under "Returned by riders" with **KEEP · A1** and a High / Medium / Low chance, and a purple **Put on shelf A1** card appears under "Do now". Tap **✓ Done**. Press **हिंदी** to show the Hindi version, then switch back.
5. **A nearby order.** Set speed to **Fast** and tick **Auto-rider**. Within a minute or two, a green **Take out A… → give to rider** card appears: a real order nearby matched a shelf parcel. *"₹21 local delivery instead of a ₹120 return."*
6. **Space is short.** Set **Shelf: 10 slots**. Orange **Take out → return bag · making space** cards appear when a better parcel needs the slot.
7. **Manager.** End on the right-hand screen: money saved so far, where refused parcels went, and the 3-month estimate with the cost per refused parcel (₹120 → about ₹40–80 in Bengaluru). *"Based on one seller's orders; Valmo's volume is much larger, and the per-parcel saving is what scales."*
8. Use **Lucknow** or **Kanpur** to show the honest limit: in thin districts few parcels find a nearby buyer, so roll out to dense districts first.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found (Windows) | reinstall Python and tick "Add python.exe to PATH" |
| `No module named flask` | activate `.venv`, then `pip install -r app/requirements.txt` |
| Port 5000 already in use (common on Mac) | run with another port: `PORT=5050 python app/server.py` (Mac), or `set PORT=5050` then `python app/server.py` (Windows) |
| `FileNotFoundError … 04_prepare_orders.py first` | run `python run_all.py` from the top |
| Phone can't open the laptop address | same Wi-Fi? allow Python in the firewall, or use the cloudflared link |
| Screens stop updating | the small dot in the top bar turns red when the server isn't reachable; restart `app/server.py` |
| Notifications stop | either the district reached the end of the real data (the button shows "■ Ended"), or "Next refused parcel" borrowed the upcoming ones; press **Reset** |
| Buttons on the hub don't respond | press **Ctrl + F5** to load the latest files |
