import requests
import os
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

GAS_URL = "https://script.google.com/macros/s/AKfycbxNKUunxKrDFqQi7cn_EzoQGNsqkb9cdkqRR3JeCVXPPHyiPml4YaLUdFfhBfCMBZv9/exec"
session = requests.Session()

def scrape_isp(q_id):
    try:
        r = session.get(f"https://ispbill.com/pay.php?c=1021&q={q_id}", timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        tds = soup.find_all('td')
        if len(tds) > 13:
            u_id = str(tds[3].get_text(strip=True))
            if len(u_id) == 10 and u_id[0] != '0': u_id = '0' + u_id
            return {
                "name": tds[1].get_text(strip=True),
                "user_id": u_id,
                "billing_id": str(q_id) if len(str(q_id)) == 7 else "",
                "package": tds[7].get_text(strip=True),
                "expire": tds[13].get_text(strip=True)
            }
    except: pass
    return None

def sync_task(u):
    if not u.get('name') or u.get('name') == "undefined" or u.get('name') == "":
        sid = u.get('billing_id') if u.get('billing_id') else u.get('user_id')
        data = scrape_isp(sid)
        if data: session.post(GAS_URL, json={"action": "add_or_update", **data})

@app.route('/sync_sheet')
def sync_sheet():
    users = session.get(GAS_URL).json()
    with ThreadPoolExecutor(max_workers=10) as exe: exe.map(sync_task, users)
    return jsonify({"success": True})

@app.route('/get_all_users')
def get_all_users(): return session.get(GAS_URL).text

@app.route('/fetch_user')
def fetch_user():
    id_param = request.args.get('id')
    data = scrape_isp(id_param)
    if data: session.post(GAS_URL, json={"action": "add_or_update", **data})
    return jsonify({"success": True}) if data else jsonify({"success": False})

@app.route('/delete_user')
def delete_user():
    id_param = request.args.get('id')
    session.post(GAS_URL, json={"action": "delete", "user_id": str(id_param)})
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
