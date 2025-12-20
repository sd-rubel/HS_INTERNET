import requests
import os
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

GAS_URL = "https://script.google.com/macros/s/AKfycbxNKUunxKrDFqQi7cn_EzoQGNsqkb9cdkqRR3JeCVXPPHyiPml4YaLUdFfhBfCMBZv9/exec"

# দ্রুত ডাটা পাঠানোর জন্য সেশন ব্যবহার
session = requests.Session()

def scrape_isp(q_id):
    url = f"https://ispbill.com/pay.php?c=1021&q={q_id}"
    try:
        r = session.get(url, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        all_td = soup.find_all('td')
        if len(all_td) > 13:
            u_id = all_td[3].get_text(strip=True)
            b_id = str(q_id) if len(str(q_id)) == 7 else ""
            
            # ১১ ডিজিট পূর্ণ করা (০ যুক্ত করা)
            u_id_str = str(u_id)
            if len(u_id_str) == 10 and u_id_str[0] != '0':
                u_id_str = '0' + u_id_str

            return {
                "name": all_td[1].get_text(strip=True),
                "user_id": u_id_str,
                "billing_id": str(b_id),
                "package": all_td[7].get_text(strip=True),
                "expire": all_td[13].get_text(strip=True)
            }
    except:
        pass
    return None

def sync_worker(u):
    name = str(u.get('name', '')).strip()
    uid = str(u.get('user_id', '')).strip()
    bid = str(u.get('billing_id', '')).strip()
    
    # যদি নাম না থাকে তবেই আপডেট করবে
    if name == "" or name == "undefined":
        sid = bid if (bid != "" and bid != "undefined") else uid
        if sid:
            fresh = scrape_isp(sid)
            if fresh:
                session.post(GAS_URL, json={"action": "add_or_update", **fresh})

@app.route('/sync_sheet')
def sync_sheet():
    try:
        users = session.get(GAS_URL).json()
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(sync_worker, users)
        return jsonify({"success": True})
    except:
        return jsonify({"success": False})

@app.route('/delete_user')
def delete_user():
    id_param = request.args.get('id')
    # মোবাইল নম্বর বা বিলিং আইডি যাই হোক স্ট্রিং হিসেবে ডিলিট রিকোয়েস্ট পাঠানো
    r = session.post(GAS_URL, json={"action": "delete", "user_id": str(id_param)})
    return r.text

@app.route('/get_all_users')
def get_all_users():
    return session.get(GAS_URL).text

@app.route('/fetch_user')
def fetch_user():
    id_param = request.args.get('id')
    new_data = scrape_isp(id_param)
    if new_data:
        session.post(GAS_URL, json={"action": "add_or_update", **new_data})
        return jsonify({"success": True, **new_data})
    return jsonify({"success": False})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
