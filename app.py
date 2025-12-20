import requests
import os
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# আপনার নতুন Google Apps Script URL
GAS_URL = "https://script.google.com/macros/s/AKfycbxNKUunxKrDFqQi7cn_EzoQGNsqkb9cdkqRR3JeCVXPPHyiPml4YaLUdFfhBfCMBZv9/exec"

def scrape_isp(q_id):
    url = f"https://ispbill.com/pay.php?c=1021&q={q_id}"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        all_td = soup.find_all('td')
        if len(all_td) > 13:
            u_id = all_td[3].get_text(strip=True)
            b_id = str(q_id) if len(str(q_id)) == 7 else ""
            
            return {
                "name": all_td[1].get_text(strip=True),
                "user_id": u_id,
                "billing_id": b_id,
                "package": all_td[7].get_text(strip=True),
                "expire": all_td[13].get_text(strip=True)
            }
    except Exception as e:
        print(f"Scraping error: {e}")
    return None

@app.route('/')
def home():
    return "ISP Backend with Google Sheets is Running!", 200

@app.route('/fetch_user')
def fetch_user():
    id_param = request.args.get('id')
    if not id_param:
        return jsonify({"success": False})
        
    new_data = scrape_isp(id_param)
    if new_data:
        # Google Sheet এ ডাটা পাঠানো
        payload = {
            "action": "add_or_update",
            **new_data
        }
        requests.post(GAS_URL, json=payload)
        return jsonify({"success": True, **new_data})
    return jsonify({"success": False})

@app.route('/sync_sheet')
def sync_sheet():
    try:
        # Google Sheet থেকে সব ইউজার পড়া
        users = requests.get(GAS_URL).json()
        updated_count = 0
        for u in users:
            search_id = u.get('billing_id') if u.get('billing_id') else u.get('user_id')
            if search_id:
                fresh = scrape_isp(search_id)
                if fresh:
                    payload = {"action": "add_or_update", **fresh}
                    requests.post(GAS_URL, json=payload)
                    updated_count += 1
        return jsonify({"success": True, "updated": updated_count})
    except:
        return jsonify({"success": False, "updated": 0})

@app.route('/get_all_users')
def get_all_users():
    try:
        r = requests.get(GAS_URL)
        return r.text
    except:
        return jsonify([])

@app.route('/delete_user')
def delete_user():
    id_param = request.args.get('id')
    payload = {
        "action": "delete",
        "user_id": id_param
    }
    r = requests.post(GAS_URL, json=payload)
    return r.text

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
