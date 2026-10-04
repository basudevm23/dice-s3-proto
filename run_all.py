"""Runs every offline step in order. Internet is needed only for step 1.1 (first run).
Play Store / Reddit collection and the survey are run separately (see README)."""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    "step1_collect/01_get_data.py",
    "step2_prepare/04_prepare_orders.py",
    "step2_prepare/05_survey_analysis.py",       # skipped politely if no survey CSV yet
    "step3_analysis/07_backtest_match_rate.py",
    "step4_prototypes/p1_rider_screen.py",
    "step4_prototypes/p2_hub_shelf.py",
    "step4_prototypes/p3_savings_card.py",
    "step4_prototypes/build_live_data.py",
]
for s in STEPS:
    print(f"\n========== {s} ==========")
    try:
        runpy.run_path(str(ROOT / s), run_name="__main__")
    except SystemExit as e:
        print(f"(stopped: {e})")
