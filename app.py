import requests
import os
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# আপনার SheetDB URL
SHEETDB_URL = "https://sheetdb.io/api/v1/aw2yzluj9o4xc"

def scrape_isp(q_id):
    url = f"https://ispbill.com/pay.php?c=1021&q={q_id}"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        all_td = soup.find_all('td')
        if len(all_td) > 13:
            u_id = all_td[3].get_text(strip=True) # ১১ ডিজিট ফোন নম্বর
            # ৭ ডিজিট আইডি হলে সেটিই Billing ID
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
    # এটি Cron-job কে সার্ভার সচল রাখতে সাহায্য করবে
    return "ISP Backend is Running!", 200

@app.route('/fetch_user')
def fetch_user():
    id_param = request.args.get('id')
    if not id_param:
        return jsonify({"success": False, "message": "No ID provided"})
        
    new_data = scrape_isp(id_param)
    if new_data:
        # শিটে ইউজার আইডি (১১ ডিজিট) দিয়ে চেক করা
        check = requests.get(f"{SHEETDB_URL}/search?user_id={new_data['user_id']}").json()
        if isinstance(check, list) and len(check) > 0:
            requests.put(f"{SHEETDB_URL}/user_id/{new_data['user_id']}", json={"data": new_data})
        else:
            requests.post(SHEETDB_URL, json={"data": [new_data]})
        return jsonify({"success": True, **new_data})
    return jsonify({"success": False})

@app.route('/sync_sheet')
def sync_sheet():
    try:
        users = requests.get(SHEETDB_URL).json()
        updated_count = 0
        for u in users:
            # যদি নাম না থাকে বা অটো আপডেট প্রয়োজন হয়
            if not u.get('name') or u.get('name') == "":
                search_id = u.get('billing_id') if u.get('billing_id') else u.get('user_id')
                if search_id:
                    fresh = scrape_isp(search_id)
                    if fresh:
                        identifier = "billing_id" if len(str(search_id)) == 7 else "user_id"
                        requests.put(f"{SHEETDB_URL}/{identifier}/{search_id}", json={"data": fresh})
                        updated_count += 1
        return jsonify({"success": True, "updated": updated_count})
    except:
        return jsonify({"success": False, "updated": 0})

@app.route('/get_all_users')
def get_all_users():
    return requests.get(SHEETDB_URL).text

@app.route('/delete_user')
def delete_user():
    id_param = request.args.get('id')
    search_col = "billing_id" if len(str(id_param)) == 7 else "user_id"
    return requests.delete(f"{SHEETDB_URL}/{search_col}/{id_param}").text

if __name__ == "__main__":
    # Render এর জন্য ডাইনামিক পোর্ট সেটআপ
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
      
