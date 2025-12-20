import requests
import os
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

# আপনার গুগল অ্যাপস স্ক্রিপ্ট ইউআরএল
GAS_URL = "https://script.google.com/macros/s/AKfycbxNKUunxKrDFqQi7cn_EzoQGNsqkb9cdkqRR3JeCVXPPHyiPml4YaLUdFfhBfCMBZv9/exec"

def scrape_isp(q_id):
    url = f"https://ispbill.com/pay.php?c=1021&q={q_id}"
    try:
        r = requests.get(url, timeout=7)
        soup = BeautifulSoup(r.text, 'html.parser')
        all_td = soup.find_all('td')
        if len(all_td) > 13:
            u_id = all_td[3].get_text(strip=True)
            # ৭ ডিজিট হলে সেটি বিলিং আইডি হিসেবে গণ্য হবে
            b_id = str(q_id) if len(str(q_id)) == 7 else ""
            
            return {
                "name": all_td[1].get_text(strip=True),
                "user_id": str(u_id), 
                "billing_id": str(b_id),
                "package": all_td[7].get_text(strip=True),
                "expire": all_td[13].get_text(strip=True)
            }
    except:
        pass
    return None

def sync_single_user(u):
    # যদি নাম খালি থাকে, তবেই এটি ম্যানুয়াল এন্ট্রি হিসেবে ধরা হবে
    name = str(u.get('name', '')).strip()
    if name == "" or name == "undefined":
        uid = str(u.get('user_id', '')).strip()
        bid = str(u.get('billing_id', '')).strip()
        
        # বিলিং আইডি অগ্রাধিকার পাবে, না থাকলে ইউজার আইডি
        search_id = bid if (bid != "" and bid != "undefined") else uid
        
        if search_id:
            fresh = scrape_isp(search_id)
            if fresh:
                requests.post(GAS_URL, json={"action": "add_or_update", **fresh})
                return True
    return False

@app.route('/')
def home():
    return "ISP Backend Multi-Threaded is Running!", 200

@app.route('/sync_sheet')
def sync_sheet():
    try:
        r = requests.get(GAS_URL)
        users = r.json()
        # ৫টি থ্রেড একসাথে কাজ করবে যা সিঙ্কিং টাইম অনেক কমিয়ে দিবে
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(sync_single_user, users)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/get_all_users')
def get_all_users():
    return requests.get(GAS_URL).text

@app.route('/fetch_user')
def fetch_user():
    id_param = request.args.get('id')
    new_data = scrape_isp(id_param)
    if new_data:
        requests.post(GAS_URL, json={"action": "add_or_update", **new_data})
        return jsonify({"success": True, **new_data})
    return jsonify({"success": False})

@app.route('/delete_user')
def delete_user():
    id_param = request.args.get('id')
    requests.post(GAS_URL, json={"action": "delete", "user_id": id_param})
    return jsonify({"success": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
