import os
import time
import requests
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)

GAS_URL = "https://script.google.com/macros/s/AKfycbxNKUunxKrDFqQi7cn_EzoQGNsqkb9cdkqRR3JeCVXPPHyiPml4YaLUdFfhBfCMBZv9/exec"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# -------------------- CACHE --------------------
CACHE = {}
CACHE_TTL = 300  # 5 minutes


def get_cached(uid):
    c = CACHE.get(uid)
    if c and time.time() - c["t"] < CACHE_TTL:
        return c["d"]
    return None


def set_cache(uid, data):
    CACHE[uid] = {"d": data, "t": time.time()}


# -------------------- SCRAPER --------------------
def scrape_isp(q_id):
    cached = get_cached(q_id)
    if cached:
        return cached

    try:
        r = requests.get(
            f"https://ispbill.com/pay.php?c=1021&q={q_id}",
            headers=HEADERS,
            timeout=6
        )
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        tds = soup.find_all("td")
        if len(tds) < 14:
            return None

        user_id = tds[3].get_text(strip=True)
        if len(user_id) == 10 and not user_id.startswith("0"):
            user_id = "0" + user_id

        data = {
            "name": tds[1].get_text(strip=True),
            "user_id": user_id,
            "billing_id": str(q_id) if len(str(q_id)) == 7 else "",
            "package": tds[7].get_text(strip=True),
            "expire": tds[13].get_text(strip=True)
        }

        set_cache(q_id, data)
        return data

    except Exception as e:
        print("SCRAPE ERROR:", e)
        return None


# -------------------- GAS HELPERS --------------------
def gas_get_all():
    r = requests.get(GAS_URL, timeout=10)
    r.raise_for_status()
    return r.json()


def gas_post(payload):
    r = requests.post(GAS_URL, json=payload, timeout=10)
    r.raise_for_status()
    return True


# -------------------- ROUTES --------------------
@app.route("/get_all_users")
def get_all_users():
    try:
        return jsonify(gas_get_all())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/fetch_user")
def fetch_user():
    uid = request.args.get("id", "").strip()
    if not uid.isdigit() or len(uid) < 7:
        return jsonify({"success": False, "error": "Invalid ID"}), 400

    data = scrape_isp(uid)
    if not data:
        return jsonify({"success": False})

    gas_post({"action": "add_or_update", **data})
    return jsonify({"success": True, "data": data})


@app.route("/delete_user")
def delete_user():
    uid = request.args.get("id", "").strip()
    if not uid:
        return jsonify({"success": False}), 400

    gas_post({"action": "delete", "user_id": uid})
    return jsonify({"success": True})


@app.route("/sync_sheet")
def sync_sheet():
    try:
        users = gas_get_all()
    except:
        return jsonify({"success": False}), 500

    def job(u):
        if u.get("name"):
            return None
        sid = u.get("billing_id") or u.get("user_id")
        if not sid:
            return None

        d = scrape_isp(sid)
        if d:
            gas_post({"action": "add_or_update", **d})
        return True

    with ThreadPoolExecutor(max_workers=4) as exe:
        list(as_completed([exe.submit(job, u) for u in users]))

    return jsonify({"success": True})


# -------------------- MAIN --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
