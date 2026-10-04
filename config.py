"""
config.py - every number the project uses, in one place, each tagged with its source.

Source tags
  CASE_PACK  : Meesho DICE S3 case pack (treated as true)
  DATASET    : measured from the Kaggle Amazon India sales dataset
  INDUSTRY   : published figure (URL given)
  DECK       : our own final presentation
  SURVEY     : our Google Form (filled in by step2_prepare/05_survey_analysis.py)
  ASSUMPTION : our working assumption, shown as such and tested both ways

If you change a number, change it here only.
"""

# ---------------------------------------------------------------- case pack
CASE_PACK = {
    "cod_share": 0.80,
    "rto_cod": 0.20,
    "rto_prepaid": 0.05,
    "forward_cost": 50,      # Rs per successful delivery
    "reverse_cost": 120,     # Rs per RTO shipment (individual return)
    # cost per leg (sums to Rs 50)
    "legs": {"FM_HUB": 4, "FM_CARTING": 2, "FMSC": 5, "NLH": 8, "LMSC": 5, "RLH": 5, "LMDC": 21},
    # share of orders returned undelivered by distance from the delivery hub
    "rto_by_distance_km": {2: 0.15, 5: 0.17, 10: 0.22},
}
BLENDED_RTO = CASE_PACK["cod_share"] * CASE_PACK["rto_cod"] + (1 - CASE_PACK["cod_share"]) * CASE_PACK["rto_prepaid"]  # 0.17

# Derived costs (all from case-pack legs)
COST = {
    # a held parcel re-delivered from the last-mile delivery centre = one more LMDC leg
    "local_redelivery_from_lmdc": CASE_PACK["legs"]["LMDC"],                                  # Rs 21
    # held at the destination sort centre = regional line haul + LMDC leg
    "local_redelivery_from_lmsc": CASE_PACK["legs"]["RLH"] + CASE_PACK["legs"]["LMDC"],       # Rs 26
    # one more delivery attempt = one more LMDC leg
    "reattempt": CASE_PACK["legs"]["LMDC"],                                                   # Rs 21
    "individual_return": CASE_PACK["reverse_cost"],                                           # Rs 120
    # a batched return moves like forward freight (Rs 50) at best, like a lone return (Rs 120) at worst
    "batched_return_low": CASE_PACK["forward_cost"],                                          # Rs 50
    "batched_return_high": CASE_PACK["reverse_cost"],                                         # Rs 120
    "exchange_forward_leg": CASE_PACK["forward_cost"],                                        # Rs 50, replacement sent from seller
    "kirana_incentive": 20,                                                                   # DECK: Rs 20 kirana pickup incentive
}

# Holding cost: INDUSTRY rent x ASSUMPTION on space per parcel
HOLDING = {
    "rent_per_sqft_month": 20,   # INDUSTRY: Vestian H1 2025, top-7 cities Rs 18-31/sq ft/month
    "rent_source": "https://realtynmore.com/warehousing-rentals-remained-largely-stable-in-h1-2025-amid-fluctuating-market-vestian",
    "parcels_per_sqft": 4,       # ASSUMPTION: small poly-bag parcels on 4-level shelving incl. aisle space
}
HOLDING["per_parcel_per_day"] = HOLDING["rent_per_sqft_month"] / HOLDING["parcels_per_sqft"] / 30   # ~Rs 0.17

# ------------------------------------------------------------ survey usage
# The survey is supporting evidence only. Set False to ignore it everywhere (industry ranges are used instead).
USE_SURVEY = True

# ------------------------------------------------------------ model settings
WINDOW_DAYS = 7          # how long a refused parcel may wait for a nearby buyer (shown: 3, 7, 14)
REFUSAL_LAG_DAYS = 4     # ASSUMPTION: days from order to refusal reaching the hub (dataset has no delivery dates)
HISTORY_DAYS = 30        # demand history the hold-or-return rule looks back at
DEFAULT_K = [1, 3, 5]
HOLD_THRESHOLD = 0.05   # hold a parcel if its chance of a nearby buyer within the window is at least 5%
DEMO_SHELF_SLOTS = 40   # DEMO SETTING for the live prototype (no hub data); change freely    # demand multiplier for "any seller" matching; k=1 is measured (one seller)
RETURNED_STATUSES = ["Shipped - Returned to Seller", "Shipped - Returning to Seller", "Shipped - Rejected by Buyer"]
CANCELLED_STATUSES = ["Cancelled"]

# Districts to feature (first 3 digits of the PIN = India Post sorting district)
DISTRICTS = {"208": "Kanpur", "226": "Lucknow", "560": "Bengaluru"}

# --------------------------------------------------------- refusal reasons
# Shares of all RTO. DECK values are from our presentation; LOW/HIGH span the published sources.
# Refusal at the door is one group in every source; the split inside it comes from the SURVEY only.
REASON_GROUPS = [
    {"id": "refused", "label": "Refused at the door", "deck": 0.40, "low": 0.15, "high": 0.40,
     "sources": ["DECK 40%", "Pragma ~37% of NDRs", "shipsagar 15-20% of NDRs"]},
    {"id": "unavailable", "label": "Customer not available", "deck": 0.28, "low": 0.25, "high": 0.30,
     "sources": ["DECK 28%", "shipsagar 25-30% of NDRs"]},
    {"id": "address", "label": "Address problem", "deck": 0.18, "low": 0.14, "high": 0.25,
     "sources": ["DECK 18%", "Pragma ~14%", "shipsagar 20-25%"]},
    {"id": "fake", "label": "Fake order", "deck": 0.09, "low": 0.09, "high": 0.09, "sources": ["DECK 9% (single source)"]},
    {"id": "carrier", "label": "Carrier-side miss", "deck": 0.05, "low": 0.05, "high": 0.05, "sources": ["DECK 5% (single source)"]},
]

# Reason codes the rider picks (P1). 'group' links each to the shares above.
# fix_cost is from case-pack legs or the deck. success_default is used ONLY when no survey data exists.
REASON_CODES = [
    {"id": "no_cash",       "group": "refused",     "label": "No cash right now",
     "fix": "Pay by UPI at the door", "fix_cost": 0, "cost_source": "same trip",
     "survey_q": "C1", "success_default": None},
    {"id": "changed_mind",  "group": "refused",     "label": "Changed mind / doesn't need it",
     "fix": "No fix at the door: send to hub shelf", "fix_cost": 0, "cost_source": "-",
     "survey_q": None, "success_default": 0.0},
    {"id": "fit_quality",   "group": "refused",     "label": "Wrong size / not as expected",
     "fix": "Offer an exchange (refused unit goes to hub shelf)", "fix_cost": COST["exchange_forward_leg"],
     "cost_source": "CASE_PACK forward Rs 50", "survey_q": "C5", "success_default": None},
    {"id": "not_home",      "group": "unavailable", "label": "Not home / not answering",
     "fix": "Leave with neighbour or partner kirana", "fix_cost": COST["kirana_incentive"],
     "cost_source": "DECK Rs 20 kirana incentive", "survey_q": "C3", "success_default": None},
    {"id": "reschedule",    "group": "unavailable", "label": "Asks to come another day",
     "fix": "Book a new slot (one more attempt)", "fix_cost": COST["reattempt"],
     "cost_source": "CASE_PACK LMDC leg Rs 21", "survey_q": "C2", "success_default": None},
    {"id": "address",       "group": "address",     "label": "Can't find the address",
     "fix": "Customer drops map pin on WhatsApp, re-attempt", "fix_cost": COST["reattempt"],
     "cost_source": "CASE_PACK LMDC leg Rs 21", "survey_q": "C4", "success_default": None},
    {"id": "fake",          "group": "fake",        "label": "Customer says they never ordered",
     "fix": "No fix: send to hub shelf, flag account", "fix_cost": 0, "cost_source": "-",
     "survey_q": None, "success_default": 0.0},
    {"id": "carrier",       "group": "carrier",     "label": "Could not attempt (our side)",
     "fix": "Re-attempt next day", "fix_cost": COST["reattempt"],
     "cost_source": "CASE_PACK LMDC leg Rs 21", "survey_q": None, "success_default": None},
]
# Published recoverability of failed deliveries, used as the fallback range for fix success
INDUSTRY_NDR_RECOVERY = (0.40, 0.50)   # DECK cites 40-50% of NDRs recoverable

# Stated-intent calibration (market-research rule of thumb)
INTENT_WEIGHTS = {"Definitely yes": 0.75, "Probably yes": 0.25, "Probably not": 0.0, "Definitely not": 0.0}

# --------------------------------------------------------------- sources
SOURCES = {
    "case_pack": "Meesho DICE S3 Valmo case study (provided)",
    "dataset": "https://www.kaggle.com/datasets/thedevastator/unlock-profits-with-e-commerce-sales-data",
    "pincodes": "https://www.data.gov.in/catalog/all-india-pincode-directory (mirror: github.com/dropdevrahul/pincodes-india)",
    "meesho_ipo": "https://thedailybrief.zerodha.com/p/inside-meeshos-ipo",
    "amazon_rto_cost": "https://shipping.amazon.in/blog/what-is-rto-how-to-reduce-return-to-origin",
    "pragma_ndr": "https://bepragma.ai/blogs/ndr-management",
    "shipsagar_ndr": "https://shipsagar.com/what-is-ndr-in-courier/",
    "vestian_rent": HOLDING["rent_source"],
}
