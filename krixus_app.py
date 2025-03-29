from flask import Flask, render_template, request, jsonify, Response
from flask_httpauth import HTTPBasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time
from datetime import datetime
import re
import random
import os
import logging
import requests

app = Flask(__name__)
auth = HTTPBasicAuth()
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["100 per hour"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy news data
dummy_news_hindi = [
    "NDTV: DTC ko 14 hazar crore ka ghata hua.",
    "Times of India: Delhi mein bus kam hone se dikkat.",
    "ANI: CM ne report pesh ki."
]
dummy_news_english = [
    "NDTV: DTC lost 14,000 crore.",
    "Times of India: Less buses in Delhi caused loss.",
    "ANI: CM shared a report."
]

# Users ka dictionary (abhi env se, baad mein admin se update hoga)
users = {
    os.environ.get("USER1_NAME", "aniket"): os.environ.get("USER1_PASS", "krixus123"),
    os.environ.get("USER2_NAME", "user1"): os.environ.get("USER2_PASS", "pass1"),
    os.environ.get("USER3_NAME", "user2"): os.environ.get("USER3_PASS", "pass2"),
    os.environ.get("USER4_NAME", "user3"): os.environ.get("USER4_PASS", "pass3"),
    os.environ.get("USER5_NAME", "user4"): os.environ.get("USER5_PASS", "pass4"),
    os.environ.get("USER6_NAME", "user5"): os.environ.get("USER6_PASS", "pass5")
}

# Admin credentials (sirf tu use karega)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "supersecret123"  # Yeh change kar sakta hai

@auth.verify_password
def verify_password(username, password):
    if username in users and users[username] == password:
        logger.info(f"{username} sahi se andar aaya")
        return username
    logger.warning(f"{username} galat password dala")
    return None

def is_hindi_word(word):
    return bool(re.search(r'[\u0900-\u097F]', word))

def sanitize_input(command):
    return re.sub(r'[<>{}[\]()=;]', '', command)

def verify_recaptcha(response):
    secret_key = os.environ.get("RECAPTCHA_SECRET_KEY", "default-secret")
    data = {
        'secret': secret_key,
        'response': response
    }
    r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
    result = r.json()
    return result.get('success', False)

def search_web(query, command):
    news_part = command.split("क्या है")[0].strip() if "क्या है" in command else command
    selected_news = random.sample(dummy_news_hindi if is_hindi_word(news_part.split()[0]) else dummy_news_english, 3)
    suffix = f" Zyada jaan-ne ke liye Google pe '{query}' search kar!" if is_hindi_word(news_part.split()[0]) else f" For more, search '{query}' on Google!"
    return f"{news_part}: " + " | ".join(selected_news) + suffix

def get_time(lang):
    current_time = datetime.now()
    hour_24 = int(current_time.strftime("%H"))
    hour_12 = int(current_time.strftime("%I"))
    minutes = current_time.strftime("%M")
    seconds = current_time.strftime("%S")
    am_pm = current_time.strftime("%p")
    if lang == "hindi":
        period = "subah" if 5 <= hour_24 < 12 else "dopahar" if 12 <= hour_24 < 17 else "shaam" if 17 <= hour_24 < 20 else "raat"
        return f"Abhi {period} ke {hour_12} baje {minutes} minute {seconds} second {am_pm} hai."
    else:
        period = "morning" if 5 <= hour_24 < 12 else "afternoon" if 12 <= hour_24 < 17 else "evening" if 17 <= hour_24 < 20 else "night"
        return f"It’s {period} {hour_12}:{minutes}:{seconds} {am_pm} now."

@app.route('/')
@auth.login_required
@limiter.limit("100 per hour")
def index():
    return render_template('index.html', recaptcha_site_key=os.environ.get("RECAPTCHA_SITE_KEY", "default-key"))

@app.route('/ask', methods=['POST'])
@auth.login_required
@limiter.limit("100 per hour")
def ask():
    recaptcha_response = request.form.get('g-recaptcha-response')
    if not recaptcha_response or not verify_recaptcha(recaptcha_response):
        return jsonify({'response': 'Please complete the CAPTCHA!'})
    command = sanitize_input(request.form['command'].lower().strip())
    logger.info(f"{auth.current_user()} ne poochha: {command}")
    if "krixus" not in command:
        response = "Shuru mein 'Krixus' bol please!"
    else:
        command = command.replace("krixus", "").strip()
        lang = "hindi" if is_hindi_word(command.split()[0]) else "english"
        if "न्यूज़" in command or "news" in command:
            response = search_web("latest news today", command)
        elif command == "टाइम क्या हुआ है" or command == "what’s the time":
            response = get_time(lang)
        elif command == "bye":
            response = "Bye bye, milte hain!"
        else:
            response = "Sorry, yeh samajh nahi aaya!"
    return jsonify({'response': response})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.authorization and request.authorization.username == ADMIN_USERNAME and request.authorization.password == ADMIN_PASSWORD:
        if request.method == 'POST':
            new_username = sanitize_input(request.form.get('username', ''))
            new_password = sanitize_input(request.form.get('password', ''))
            if new_username and new_password and new_username not in users:
                users[new_username] = new_password
                logger.info(f"New user added: {new_username}")
                return jsonify({'message': f'User {new_username} added successfully!'})
            return jsonify({'message': 'Username already exists or invalid input!'})
        return render_template('admin.html')
    return Response("Admin login required!", 401, {'WWW-Authenticate': 'Basic realm="Admin Login"'})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)