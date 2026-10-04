"""
server.py - the live prototype.

Run locally:   python app/server.py           -> http://localhost:5000
Hosted:        gunicorn --chdir app -w 1 --threads 8 -b 0.0.0.0:$PORT server:app

Pages
  /            start page (links + QR code for the rider phone)
  /present     all three screens side by side (for presenting)
  /rider       P1  rider's phone
  /hub         P2  hub shelf
  /savings     P3  savings card
API
  GET  /api/static            reasons, costs, projections (loaded once)
  GET  /api/state             live shared state (screens poll this every second)
  POST /api/rider/answer      {task_id, reason_id, accepted}
  POST /api/control           {action: play|pause|reset|speed|auto_rider|next_parcel, value}

IMPORTANT when hosting: use ONE worker (-w 1). The simulation lives in memory, so every
viewer must reach the same process to see the same live state.
"""
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from sim import Sim, static_payload

HERE = Path(__file__).parent
app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")
SIM = Sim(district=os.environ.get("DISTRICT", "226"))
PAGES = {"": "index.html", "present": "present.html", "rider": "rider.html", "hub": "hub.html", "savings": "savings.html"}


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
@app.get("/<page>")
def page(page=""):
    if page not in PAGES:
        return "Not found", 404
    return send_from_directory(app.static_folder, PAGES[page])


@app.get("/api/static")
def api_static():
    return jsonify(static_payload())


@app.get("/api/state")
def api_state():
    return jsonify(SIM.state())


@app.post("/api/rider/answer")
def api_answer():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(SIM.answer(body.get("task_id"), body.get("reason_id"), body.get("accepted")))


@app.post("/api/control")
def api_control():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(SIM.control(body.get("action"), body.get("value")))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Wapas Nahi live prototype:  http://localhost:{port}\n"
          f"  Presenter view:             http://localhost:{port}/present\n")
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
