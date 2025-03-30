from flask import Flask, render_template, request, jsonify, Response, session
from flask_httpauth import HTTPBasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time
from datetime import datetime, timedelta
import re
import random
import os
import logging
import requests
from PIL import Image
import io
import sympy as sp

app = Flask(__name__)
app.secret_key = "supersecretkey"
auth = HTTPBasicAuth()
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["100 per hour"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dummy_news_hindi = ["NDTV: DTC ko 14 hazar crore ka ghata hua.", "Times of India: Delhi mein bus kam hone se dikkat.", "ANI: CM ne report pesh ki."]
dummy_news_english = ["NDTV: DTC lost 14,000 crore.", "Times of India: Less buses in Delhi caused loss.", "ANI: CM shared a report."]

science_knowledge = {
    "what is gravity": "Gravity is the force that attracts objects towards each other, causing them to come together or move closer. It’s why things fall to the ground and why planets orbit the Sun. Sir Isaac Newton was the first to formulate the laws of gravity in the late 17th century, and later Albert Einstein expanded on it with his theory of General Relativity, describing gravity as the bending of space-time.",
    "what is photosynthesis": "Photosynthesis is the process by which green plants, algae, and some bacteria convert light energy into chemical energy stored in glucose. The equation is: 6CO2 + 6H2O + light energy → C6H12O6 + 6O2. It happens in the chloroplasts, where chlorophyll absorbs sunlight, takes in carbon dioxide from the air, and water from the soil, producing glucose and oxygen as byproducts."
}

users = {
    os.environ.get("USER1_NAME", "aniket"): os.environ.get("USER1_PASS", "krixus123"),
    os.environ.get("USER2_NAME", "user1"): os.environ.get("USER2_PASS", "pass1")
}

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "supersecret123"

@auth.verify_password
def verify_password(username, password):
    if username in users and users[username] == password:
        session['username'] = username
        session['login_time'] = time.time()
        session['captcha_verified'] = False  # CAPTCHA verification flag
        logger.info(f"{username} sahi se andar aaya")
        return username
    logger.warning("galat password dala")
    return None

def is_hindi_word(word):
    return bool(re.search(r'[\u0900-\u097F]', word))

def sanitize_input(command):
    return re.sub(r'[<>{}[\]()=;]', '', command)

def verify_recaptcha(response):
    secret_key = os.environ.get("RECAPTCHA_SECRET_KEY", "default-secret")
    data = {'secret': secret_key, 'response': response}
    r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
    return r.json().get('success', False)

def check_session_timeout():
    if 'login_time' in session:
        if time.time() - session['login_time'] > 300:  # 5 minutes
            session.clear()
            return False
    return True

def search_web(query, command):
    news_part = command.split("क्या है")[0].strip() if "क्या है" in command else command
    selected_news = random.sample(dummy_news_hindi if is_hindi_word(news_part.split()[0]) else dummy_news_english, 3)
    suffix = f" Zyada jaan-ne ke liye Google pe '{query}' search kar!" if is_hindi_word(news_part.split()[0]) else f" For more, search '{query}' on Google!"
    return f"{news_part}: " + " | ".join(selected_news) + suffix

def get_time(lang):
    current_time = datetime.now() + timedelta(hours=5, minutes=30)  # IST (GMT+5:30)
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

def solve_math(expression):
    try:
        # Replace % with modulo operator for SymPy
        expression = expression.replace("%", " % ")
        # Parse the expression using SymPy
        expr = sp.sympify(expression)
        result = expr.evalf()
        # Step-by-step breakdown
        steps = f"Let's solve {expression} step by step:\n"
        steps += f"Step 1: Evaluate the expression following BODMAS (Brackets, Orders, Division/Multiplication, Addition/Subtraction).\n"
        steps += f"Step 2: {expression} = {result}\n"
        # Simple ASCII diagram for visualization (e.g., for addition)
        if "+" in expression or "-" in expression:
            steps += "Diagram:\n"
            steps += "[ " + " + ".join([f"{x:>2}" for x in expression.split("+")]) + " ] = " + str(result) + "\n"
        return steps + f"Final Answer: {result}"
    except Exception as e:
        return f"Sorry, I couldn’t solve this math problem: {str(e)}"

def intelligent_response(command):
    command = command.lower().strip()
    # Math questions
    if any(op in command for op in ["+", "-", "*", "/", "%"]):
        math_expression = re.search(r'[\d+\-*/%]+', command)
        if math_expression:
            return solve_math(math_expression.group())
    # Science questions
    for question, answer in science_knowledge.items():
        if question in command:
            return answer
    # General knowledge or random questions
    if "who is" in command or "kaun hai" in command:
        name = command.replace("who is", "").replace("kaun hai", "").strip()
        return f"{name} ke baare mein: Yeh ek famous personality hai. Zyada jaan-ne ke liye Wikipedia pe padh sakte ho!" if is_hindi_word(command) else f"About {name}: This is a famous personality. You can read more on Wikipedia!"
    elif "what is" in command or "kya hai" in command:
        thing = command.replace("what is", "").replace("kya hai", "").strip()
        return f"{thing} ek interesting cheez hai. Iske baare mein Wikipedia pe padh sakte ho!" if is_hindi_word(command) else f"{thing} is an interesting thing. You can read more about it on Wikipedia!"
    elif "how to" in command or "kaise" in command:
        task = command.replace("how to", "").replace("kaise", "").strip()
        steps = f"Here’s how to {task} step by step:\n"
        steps += "Step 1: Gather all necessary materials.\n"
        steps += "Step 2: Follow a detailed guide on a tutorial website like wikiHow!\n"
        return steps
    else:
        return "Mujhe samajh nahi aaya, thodi aur detail do!" if is_hindi_word(command) else "I didn’t understand, please give more details!"

@app.route('/')
@auth.login_required
@limiter.limit("100 per hour")
def index():
    if not check_session_timeout():
        return Response("Session expired, please log in again!", 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
    show_captcha = not session.get('captcha_verified', False)
    return render_template('index.html', recaptcha_site_key=os.environ.get("RECAPTCHA_SITE_KEY", "default-key"), show_captcha=show_captcha)

@app.route('/ask', methods=['POST'])
@auth.login_required
@limiter.limit("100 per hour")
def ask():
    if not check_session_timeout():
        return jsonify({'response': 'Session expired, please log in again!'})
    # CAPTCHA verification only if not already verified
    if not session.get('captcha_verified', False):
        recaptcha_response = request.form.get('g-recaptcha-response')
        if not recaptcha_response or not verify_recaptcha(recaptcha_response):
            return jsonify({'response': 'Please complete the CAPTCHA!'})
        session['captcha_verified'] = True
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
        elif "weather" in command or "mausam" in command:
            response = "Aaj ka mausam: Thoda garmi hai, 30°C ke aaspaas. Detailed mausam ke liye apne city ka naam Google pe search karo!" if lang == "hindi" else "Today’s weather: It’s a bit warm, around 30°C. For detailed weather, search your city on Google!"
        elif "joke" in command or "chutkula" in command:
            response = "Ek din maine socha ki main bahut funny hoon, phir mirror dekha aur hasi ruk gayi!" if lang == "hindi" else "I thought I was funny, then I looked in the mirror and stopped laughing!"
        elif "hello" in command or "namaste" in command:
            response = "Namaste! Kya poochhna hai?" if lang == "hindi" else "Hello! What do you want to ask?"
        else:
            response = intelligent_response(command)
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

@app.route('/ghibli', methods=['GET', 'POST'])
@auth.login_required
@limiter.limit("100 per hour")
def ghibli_converter():
    if not check_session_timeout():
        return Response("Session expired, please log in again!", 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'response': 'No file uploaded!'})
        file = request.files['file']
        if file.filename == '':
            return jsonify({'response': 'No file selected!'})
        deepai_api_key = os.environ.get("DEEPAI_API_KEY", "")
        if not deepai_api_key:
            return jsonify({'response': 'DeepAI API key not configured!'})
        files = {'image': (file.filename, file.read())}
        response = requests.post(
            "https://api.deepai.org/api/toonify",
            files=files,
            headers={'api-key': deepai_api_key}
        )
        if response.status_code != 200:
            return jsonify({'response': 'Error converting image with DeepAI!'})
        result_url = response.json().get('output_url')
        if not result_url:
            return jsonify({'response': 'No result from DeepAI!'})
        image_response = requests.get(result_url)
        return Response(image_response.content, mimetype='image/png')
    return render_template('ghibli.html')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)