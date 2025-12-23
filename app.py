import os, time, requests
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

GAS_URL = "https://script.google.com/macros/s/AKfycbxNKUunxKrDFqQi7cn_EzoQGNsqkb9cdkqRR3JeCVXPPHyiPml4YaLUdFfhBfCMBZv9/exec"

HEADERS = {"User-Agent": "Mozilla/5.0"}

CACHE = {}
CACHE_TTL = 300  # 5 min


def scrape_isp(q):
    c = CACHE.get(q)
    if c and time.time() - c["t"] < CACHE_TTL:
        return c["d"]

    try:
        r = requests.get(
            f"https://ispbill.com/pay.php?c=1021&q={q}",
            headers=HEADERS,
            timeout=6
        )
        soup = BeautifulSoup(r.text, "html.parser")
        tds = soup.find_all("td")
        if len(tds) < 14:
            return None

        uid = tds[3].get_text(strip=True)
        if len(uid) == 10 and not uid.startswith("0"):
            uid = "0" + uid

        data = {
            "name": tds[1].get_text(strip=True),
            "user_id": uid,
            "billing_id": str(q) if len(str(q)) == 7 else "",
            "package": tds[7].get_text(strip=True),
            "expire": tds[13].get_text(strip=True)
        }

        CACHE[q] = {"d": data, "t": time.time()}
        return data

    except:
        return None


@app.route("/get_all_users")
def get_all_users():
    return jsonify(requests.get(GAS_URL).json())


@app.route("/fetch_user")
def fetch_user():
    uid = request.args.get("id", "")
    if not uid.isdigit():
        return jsonify({"success": False})

    d = scrape_isp(uid)
    if not d:
        return jsonify({"success": False})

    requests.post(GAS_URL, json={"action": "add_or_update", **d})
    return jsonify({"success": True, "data": d})


@app.route("/delete_user")
def delete_user():
    uid = request.args.get("id", "")
    requests.post(GAS_URL, json={"action": "delete", "user_id": uid})
    return jsonify({"success": True})


@app.route("/sync_sheet")
def sync_sheet():
    users = requests.get(GAS_URL).json()

    def job(u):
        if u.get("name"):
            return
        sid = u.get("billing_id") or u.get("user_id")
        d = scrape_isp(sid)
        if d:
            requests.post(GAS_URL, json={"action": "add_or_update", **d})

    with ThreadPoolExecutor(max_workers=4) as ex:
        ex.map(job, users)

    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
