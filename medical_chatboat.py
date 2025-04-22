from flask import Flask, render_template, request, jsonify, session
import speech_recognition as sr
from key_functionality import PathologyBot
import os
from google.generativeai import configure
from googletrans import Translator
import json
from dotenv import load_dotenv
import requests
import logging

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24) # Required for using session

translator = Translator()

# Function to initialize the bot with the API key
def initialize_bot():
    api_key = os.getenv("google_api_key")
    if not api_key:
        print("Error: google_api_key environment variable not set.")
        return None
    try:
        configure(api_key=api_key)
        return PathologyBot(api_key)
    except Exception as e:
        print(f"Error initializing chatbot: {e}")
        return None

# Initialize bot globally
bot = initialize_bot()
if bot:
    print("Bot initialized successfully")
else:
    print("Bot initialization failed")

@app.route('/')
def index():
    if bot:
        session['language'] = 'en' # Default language
        return render_template('index.html')
    else:
        return "Error: google_api_key not set."

@app.route('/set_language', methods=['POST'])
def set_language():
    language = request.form['language']
    session['language'] = language
    return jsonify({'status': 'success'})

def translate_text(text, target_language):
    try:
        translation = translator.translate(text, dest=target_language)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

@app.route('/chat', methods=['POST'])
def chat():
    user_id = "web_user"
    message = request.form.get('message', '').strip()
    language = session.get('language', 'en')

    if not bot:
        error_text = translate_text("Error: Chatbot not initialized", language)
        return jsonify({'response': {'text': error_text}})

    bot_response = bot.get_response(user_id, message)

    try:
        response_data = json.loads(bot_response)
        translated_text = translate_text(response_data.get('text', ''), language)

        translated_buttons = []
        if 'buttons' in response_data:
            for btn in response_data['buttons']:
                translated_buttons.append({
                'text': translate_text(btn['text'], language),
                'value': btn['value']
                })

        return jsonify({'response': {'text': translated_text, 'buttons': translated_buttons}})
    except json.JSONDecodeError:
        translated_text = translate_text(bot_response, language)
        return jsonify({'response': {'text': translated_text}})

@app.route('/speech', methods=['POST'])
def speech():
    if 'audio' in request.files:
        audio_file = request.files['audio']
        language = session.get('language', 'en')

        try:
            r = sr.Recognizer()
            with sr.AudioFile(audio_file) as source:
                audio = r.record(source)
            message = r.recognize_google(audio)

            if message.lower().strip() in {'exit', 'bye', 'goodbye', 'quit'}:
                return jsonify({'response': translate_text("Goodbye! Have a nice day.", language), 'transcript': message})

            if not bot:
                return jsonify({'response': translate_text("Error: Chatbot not initialized.", language), 'transcript': message})

            if language != 'en':
                message = translate_text(message, 'en')

            response = bot.get_response("web_user", message)

            if language != 'en':
                response = translate_text(response, language)

            return jsonify({'response': response, 'transcript': message})
        except sr.UnknownValueError:
            return jsonify({'response': translate_text("Could not understand audio", language), 'transcript': ""})
        except sr.RequestError as e:
            return jsonify({'response': translate_text(f"Speech recognition error: {e}", language), 'transcript': ""})
    else:
        return jsonify({'response': translate_text("No audio file received", session.get('language', 'en')), 'transcript': ""})

# 🟢 Gupshup Webhook Endpoint
# Create a custom logger for Gupshup
gupshup_logger = logging.getLogger("GupshupWebhookLogger")
gupshup_logger.setLevel(logging.INFO)

# Create a file handler for the separate log file
gupshup_file_handler = logging.FileHandler("gupshup_webhook.log")
gupshup_file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
gupshup_file_handler.setFormatter(formatter)

# Add handler to the logger (only once)
if not gupshup_logger.hasHandlers():
    gupshup_logger.addHandler(gupshup_file_handler)

@app.route('/gupshup_webhook', methods=['POST'])
def gupshup_webhook():
    try:
        headers = dict(request.headers)
        gupshup_logger.info("Headers: %s", headers)

        data = request.get_json(force=True, silent=True)
        if data is None:
            gupshup_logger.warning("No JSON payload received.")
            return jsonify({"status": "error", "message": "No JSON data received"}), 400

        gupshup_logger.info("Incoming JSON Payload: %s", data)

        # Optional: Extract specific fields
        phone = data.get("payload", {}).get("sender", {}).get("phone")
        message = data.get("payload", {}).get("payload", {}).get("text")
        gupshup_logger.info("Phone: %s | Message: %s", phone, message)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        gupshup_logger.error("Error in webhook: %s", str(e), exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


# 🟢 Send Reply to Gupshup Function
def send_reply_to_gupshup(phone, message):
    GUPSHUP_API_URL = "https://api.gupshup.io/sm/api/v1/msg"
    GUPSHUP_APP_NAME = os.getenv("gupshup_app_name")
    GUPSHUP_API_KEY = os.getenv("gupshup_api_key")
    GUPSHUP_SOURCE = os.getenv("gupshup_source")

    payload = {
    "channel": "whatsapp",
    "source": GUPSHUP_SOURCE,
    "destination": phone,
    "message": json.dumps({"type": "text", "text": message}),
    "src.name": GUPSHUP_APP_NAME
    }

    headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "apikey": GUPSHUP_API_KEY
    }

    try:
        r = requests.post(GUPSHUP_API_URL, data=payload, headers=headers)
        print(f"Gupshup sent: {r.status_code}, {r.text}")
    except Exception as e:
        print(f"Failed to send message to Gupshup: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8585)