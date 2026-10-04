"""
sim.py - one shared, continuously running simulation that all three screens read.

The clock walks through the REAL dates of the dataset (Apr-Jun 2022). As it moves:
  * real orders in the district arrive in order (hub "new orders" feed);
  * each real returned parcel turns into a notification on the rider's phone at its real date;
  * the rider (you, or the auto-rider) logs a reason and whether the door fix worked;
  * parcels sent to the hub are scored by the hold-or-return rule (chance of a nearby buyer);
  * held parcels are matched to later real orders of the same style + size, or go to the return batch.

Nothing runs in the background: the clock moves forward each time a screen asks for the state,
so it works on any host and pauses itself when nobody is watching.
"""
import json
import random
import threading
import time
from collections import deque
from datetime import date, timedelta
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "data" / "live_data.json").read_text())
META = DATA["meta"]
COST = META["costs"]
REASONS = {r["id"]: r for r in DATA["reasons"]}
REATTEMPT_FIXES = {"reschedule", "address", "carrier"}   # these cost a trip even if they fail
# Share of matched buyers who accept a resold sealed parcel (survey D1 if 30+ answers, else 1.0)
BUYER_ACCEPTANCE = float(DATA.get("p3_assumptions", {}).get("buyer_acceptance", 1.0))
ACCEPTANCE_SOURCE = DATA.get("p3_assumptions", {}).get("buyer_acceptance_source", "not measured")
MAX_STEP_REAL_SECONDS = 3.0                              # clock never jumps more than this per poll
START_DATE = date.fromisoformat(META["start_date"])


class Sim:
    def __init__(self, district="226"):
        self.lock = threading.RLock()
        self.rng = random.Random(7)
        self.settings = {"seconds_per_day": 20, "auto_rider": True, "rider_timeout": 25,
                         "shelf_slots": META["shelf_slots"], "threshold": META["hold_threshold"],
                         "window": META["window_days"]}
        self.reset(district)

    # ------------------------------------------------------------------ setup
    def reset(self, district=None):
        with self.lock:
            if district and district in DATA["districts"]:
                self.district = district
            d = DATA["districts"][self.district]
            self.orders = d["orders"]
            self.returns = [r for r in d["returns"] if r["t"] >= META["sim_start_day"]]
            self.t = float(META["sim_start_day"])
            self.end_t = float(META["days"])
            self.oi = next((i for i, o in enumerate(self.orders) if o[0] >= self.t), len(self.orders))
            self.ri = 0
            self.playing = True
            self.ended = False
            self.last_real = time.time()
            self.tasks = []                       # parcels waiting for the rider's answer
            self.shelf = []                       # held parcels
            self.incoming = deque(maxlen=8)       # latest hub decisions
            self.ticker = deque(maxlen=16)        # latest real orders
            self.resold = deque(maxlen=8)
            self.feed = deque(maxlen=12)          # operator tasks for the hub screen (structured, translated on screen)
            self.log = deque(maxlen=40)
            self.orders_seen = 0
            self.tally = {k: 0 for k in ("refused", "fixed_at_door", "exchanged", "to_hub", "held",
                                         "returned_alone", "resold", "batched", "buyer_declined", "bumped")}
            self.money = {"closed": 0, "spent_low": 0.0, "spent_high": 0.0}
            self.version = 0
            self._log(f"Started {DATA['districts'][self.district]['name']} at {self._date_str()}")

    # ------------------------------------------------------------------ helpers
    def _date(self, t=None):
        t = self.t if t is None else t
        return START_DATE + timedelta(days=int(t))

    def _date_str(self, t=None):
        return self._date(t).strftime("%a %d %b %Y")

    def _time_str(self, t=None):
        t = self.t if t is None else t
        minutes = int((t % 1) * 24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def _log(self, text, kind="info"):
        self.log.appendleft({"t": round(self.t, 3), "when": f"{self._date(self.t).strftime('%d %b')} {self._time_str()}",
                             "text": text, "kind": kind})
        self.version += 1

    def _free_slot(self):
        used = {p.get("slot") for p in self.shelf}
        n = max(self.settings["shelf_slots"], len(self.shelf) + 1)
        for i in range(n):
            label = f"{chr(65 + i // 10)}{i % 10 + 1}"
            if label not in used:
                return label
        return f"X{len(self.shelf) + 1}"

    def _task(self, kind, p, **extra):
        self.feed.appendleft(dict({"kind": kind, "id": p["id"], "category": p["category"], "size": p["size"],
                                   "slot": p.get("slot"), "when": self._time_str(),
                                   "date": self._date().strftime("%d %b")}, **extra))

    def _close(self, low, high):
        self.money["closed"] += 1
        self.money["spent_low"] += low
        self.money["spent_high"] += high

    # ------------------------------------------------------------------ clock
    def advance(self):
        with self.lock:
            now = time.time()
            dt = min(now - self.last_real, MAX_STEP_REAL_SECONDS)
            self.last_real = now
            if self.playing and not self.ended:
                target = self.t + dt / self.settings["seconds_per_day"]
                self._run_until(target)
            if self.settings["auto_rider"]:
                for task in list(self.tasks):
                    if now - task["created_real"] >= self.settings["rider_timeout"]:
                        self._auto_answer(task)

    def _run_until(self, target):
        while True:
            nxt_o = self.orders[self.oi][0] if self.oi < len(self.orders) else float("inf")
            nxt_r = self.returns[self.ri]["t"] if self.ri < len(self.returns) else float("inf")
            nxt_e = min((p["hold_until"] for p in self.shelf), default=float("inf"))
            nxt = min(nxt_o, nxt_r, nxt_e)
            if nxt > target:
                break
            self.t = nxt
            if nxt == nxt_e:
                self._expire(next(p for p in self.shelf if p["hold_until"] == nxt_e))
            elif nxt == nxt_r:
                self._refusal(self.returns[self.ri])
                self.ri += 1
            else:
                self._order(self.orders[self.oi])
                self.oi += 1
        self.t = target
        if self.t >= self.end_t - 1e-6:
            self.t, self.ended, self.playing = self.end_t, True, False
            self._log("End of the real data period. Press Reset to start again.")

    # ------------------------------------------------------------------ events
    def _order(self, o):
        t, style, size, category = o
        self.orders_seen += 1
        hit = next((p for p in self.shelf if p["style"] == style and p["size"] == size), None)
        entry = {"when": self._time_str(t), "date": self._date(t).strftime("%d %b"), "category": category,
                 "size": size, "style": style, "match": None}
        if hit and self.rng.random() >= BUYER_ACCEPTANCE:
            # Fix 1: the buyer declines a resold parcel -> order goes to the seller as usual, parcel stays on the shelf
            self.tally["buyer_declined"] += 1
            entry["declined"] = hit["id"]
            self._log(f"Order for {category} size {size} matched {hit['id']}, but the buyer preferred a fresh unit "
                      f"(survey: {BUYER_ACCEPTANCE:.0%} accept). Parcel stays on the shelf.", "info")
            hit = None
        if hit:
            self.shelf.remove(hit)
            days = self.t - hit["held_t"]
            cost = COST["local_redelivery"] + COST["holding_per_day"] * days
            hit["parcel_cost"] += cost
            self._close(hit["parcel_cost"], hit["parcel_cost"])
            self.tally["resold"] += 1
            entry["match"] = hit["id"]
            self._task("pick", hit)
            self.resold.appendleft({"id": hit["id"], "slot": hit.get("slot"), "category": hit["category"], "size": hit["size"],
                                    "after_days": round(days, 1), "when": entry["date"]})
            self._log(f"New order for {category} size {size} filled from the shelf ({hit['id']}, held {days:.1f} days). "
                      f"Local delivery Rs {COST['local_redelivery']} instead of Rs {COST['individual_return']} return.", "match")
        self.ticker.appendleft(entry)
        self.version += 1

    def _refusal(self, r):
        task = dict(r)
        task.update({"created_t": self.t, "created_real": time.time(), "parcel_cost": 0.0,
                     "when": f"{self._date().strftime('%d %b')} {self._time_str()}"})
        self.tasks.append(task)
        self.tally["refused"] += 1
        self._log(f"Rider: customer did not take {r['category']} size {r['size']} (COD Rs {r['amount']}). Waiting for reason.", "rider")

    def _expire(self, p):
        self.shelf.remove(p)
        self._task("bag", p, why="time")
        hold = COST["holding_per_day"] * self.settings["window"]
        self._close(p["parcel_cost"] + hold + COST["batched_low"], p["parcel_cost"] + hold + COST["batched_high"])
        self.tally["batched"] += 1
        self._log(f"{p['id']} ({p['category']} {p['size']}) found no buyer in {self.settings['window']} days: joins the return batch.", "batch")

    # ------------------------------------------------------------------ rider
    def answer(self, task_id, reason_id, accepted):
        with self.lock:
            self.advance()
            task = next((x for x in self.tasks if x["id"] == task_id), None)
            if not task or reason_id not in REASONS:
                return {"ok": False, "error": "This parcel is no longer waiting (it may have been auto-answered)."}
            return self._apply_answer(task, REASONS[reason_id], bool(accepted), by="rider")

    def _auto_answer(self, task):
        ids = list(REASONS)
        weights = [max(REASONS[i]["share_of_refusals"], 1e-6) for i in ids]
        reason = REASONS[self.rng.choices(ids, weights)[0]]
        accepted = self.rng.random() < reason["success_rate"]
        self._apply_answer(task, reason, accepted, by="auto-rider")

    def _apply_answer(self, task, reason, accepted, by):
        self.tasks.remove(task)
        no_fix = reason["success_rate"] == 0 and reason["fix_cost"] == 0
        accepted = accepted and not no_fix
        who = "Auto-rider" if by == "auto-rider" else "Rider"
        if accepted and reason["id"] != "fit_quality":
            self.tally["fixed_at_door"] += 1
            self._close(reason["fix_cost"], reason["fix_cost"])
            self._log(f"{who}: '{reason['label']}' -> {reason['fix']}. Customer accepted: delivered (Rs {reason['fix_cost']}).", "door")
            self.version += 1
            return {"ok": True, "result": "delivered", "cost": reason["fix_cost"]}
        if accepted:   # exchange: order saved, refused unit still comes back
            self.tally["exchanged"] += 1
            task["parcel_cost"] += COST["exchange_forward"]
            self._log(f"{who}: wrong size -> exchange accepted. Order saved; refused unit goes to the hub.", "door")
        else:
            if reason["id"] in REATTEMPT_FIXES:
                task["parcel_cost"] += reason["fix_cost"]
            self._log(f"{who}: '{reason['label']}' -> {'no fix possible' if no_fix else 'fix declined'}. Parcel goes to the hub.", "rider")
        decision = self._hub_decide(task, reason)
        return {"ok": True, "result": "to_hub", "decision": decision}

    # ------------------------------------------------------------------ hub rule
    def _hub_decide(self, p, reason):
        self.tally["to_hub"] += 1
        p["reason"] = reason["label"]
        thr = self.settings["threshold"]
        win = self.settings["window"]
        room = len(self.shelf) < self.settings["shelf_slots"]
        weakest = min(self.shelf, key=lambda x: x["p_match"]) if self.shelf else None
        if p["p_match"] >= thr and not room and weakest and p["p_match"] > weakest["p_match"]:
            # Fix 3: shelf full -> the weakest parcel makes way and joins the return batch
            self._bump(weakest)
            room = True
            bumped = weakest["id"]
        else:
            bumped = None
        if p["p_match"] >= thr and room:
            p.update({"held_t": self.t, "hold_until": self.t + win, "slot": self._free_slot()})
            self.shelf.append(p)
            self._task("hold", p)
            self.tally["held"] += 1
            decision = "HOLD"
            why = f"{p['p_match']:.0%} chance of a nearby buyer in {win} days (rule holds at {thr:.0%} or more)"
            if bumped:
                why += f"; shelf was full, so {bumped} ({weakest['p_match']:.0%} chance) made way"
        else:
            self.tally["returned_alone"] += 1
            self._close(p["parcel_cost"] + COST["individual_return"], p["parcel_cost"] + COST["individual_return"])
            decision = "RETURN"
            self._task("return", p)
            why = (f"shelf is full and every parcel on it has a better chance than {p['p_match']:.0%}" if p["p_match"] >= thr else
                   f"only {p['p_match']:.0%} chance of a nearby buyer (below {thr:.0%}): send back now")
        self.incoming.appendleft({"id": p["id"], "slot": p.get("slot") if decision == "HOLD" else None,
                                  "category": p["category"], "size": p["size"], "style": p["style"],
                                  "p_match": p["p_match"], "decision": decision, "why": why, "reason": reason["label"],
                                  "when": f"{self._date().strftime('%d %b')} {self._time_str()}"})
        self._log(f"Hub rule: {p['id']} {p['category']} {p['size']} -> {decision} ({why}).", "hold" if decision == "HOLD" else "return")
        return {"decision": decision, "why": why, "p_match": p["p_match"]}

    def _bump(self, p):
        """Remove a held parcel early to make room; it joins the return batch."""
        self.shelf.remove(p)
        self._task("bag", p, why="space")
        hold = COST["holding_per_day"] * (self.t - p["held_t"])
        self._close(p["parcel_cost"] + hold + COST["batched_low"], p["parcel_cost"] + hold + COST["batched_high"])
        self.tally["batched"] += 1
        self.tally["bumped"] += 1
        self._log(f"{p['id']} ({p['category']} {p['size']}, {p['p_match']:.0%} chance) made way for a better parcel: joins the return batch.", "batch")

    # ------------------------------------------------------------------ controls
    def control(self, action, value=None):
        with self.lock:
            self.advance()
            if action == "play":
                self.playing = not self.ended
            elif action == "pause":
                self.playing = False
            elif action == "reset":
                self.reset(value)
            elif action == "speed" and value:
                self.settings["seconds_per_day"] = max(2, min(120, float(value)))
            elif action == "shelf" and value:
                self.settings["shelf_slots"] = int(max(3, min(500, float(value))))
            elif action == "auto_rider":
                self.settings["auto_rider"] = bool(value)
            elif action == "next_parcel" and self.ri < len(self.returns):
                # bring the next real refusal forward to now (keeps its real details)
                r = dict(self.returns[self.ri])
                r["t"] = self.t
                self.returns[self.ri] = r
                self._run_until(self.t)
            self.version += 1
            return {"ok": True}

    # ------------------------------------------------------------------ state for screens
    def state(self):
        with self.lock:
            self.advance()
            now = time.time()
            m = self.money
            closed = m["closed"]
            today = closed * COST["individual_return"]
            nxt = self.returns[self.ri]["t"] if self.ri < len(self.returns) else None
            return {
                "version": self.version,
                "district": self.district, "district_name": DATA["districts"][self.district]["name"],
                "clock": {"t": round(self.t, 4), "date": self._date_str(), "time": self._time_str(),
                          "day": min(int(self.t - META["sim_start_day"]) + 1, int(self.end_t - META["sim_start_day"])),
                          "days_total": int(self.end_t - META["sim_start_day"]),
                          "playing": self.playing, "ended": self.ended,
                          "next_refusal_in_days": None if nxt is None else round(max(0, nxt - self.t), 2)},
                "settings": dict(self.settings, buyer_acceptance=BUYER_ACCEPTANCE, acceptance_source=ACCEPTANCE_SOURCE),
                "rider": {"tasks": [{"id": x["id"], "category": x["category"], "size": x["size"], "style": x["style"],
                                     "amount": x["amount"], "pin": x["pin"], "when": x["when"],
                                     "age_seconds": round(now - x["created_real"]),
                                     "seconds_left": max(0, round(self.settings["rider_timeout"] - (now - x["created_real"])))
                                     if self.settings["auto_rider"] else None} for x in self.tasks]},
                "hub": {"incoming": list(self.incoming),
                        "feed": list(self.feed),
                        "shelf": [{"id": p["id"], "slot": p.get("slot"), "category": p["category"], "size": p["size"], "style": p["style"],
                                   "p_match": p["p_match"], "reason": p.get("reason"),
                                   "days_left": round(max(0, p["hold_until"] - self.t), 1)} for p in self.shelf],
                        "ticker": list(self.ticker), "resold": list(self.resold), "orders_seen": self.orders_seen},
                "tally": dict(self.tally, waiting_for_rider=len(self.tasks), on_shelf=len(self.shelf)),
                "money": {"closed": closed, "cost_today": today, "spent_low": round(m["spent_low"]), "spent_high": round(m["spent_high"]),
                          "per_parcel_low": round(m["spent_low"] / closed, 1) if closed else None,
                          "per_parcel_high": round(m["spent_high"] / closed, 1) if closed else None,
                          "saved_low": round(today - m["spent_high"]), "saved_high": round(today - m["spent_low"])},
                "log": list(self.log)[:14],
            }


def static_payload():
    return {"meta": META, "reasons": DATA["reasons"], "p3_assumptions": DATA["p3_assumptions"],
            "districts": {k: {"name": v["name"], "orders": len(v["orders"]), "returns": len(v["returns"]),
                              "projection": v["projection"]} for k, v in DATA["districts"].items()}}
