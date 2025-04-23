from flask import Flask, render_template, request, jsonify, session
import speech_recognition as sr
import os
from google.generativeai import configure
from deep_translator import GoogleTranslator
import json
from dotenv import load_dotenv
import requests
import logging
from test import MedicalChatbot,get_or_create_user_bot  # Import the MedicalChatbot class
import uuid

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24) # Required for using session

translator =    GoogleTranslator()

# Function to initialize the medical bot
def initialize_bot():
    api_key = os.getenv("google_api_key")
    if not api_key:
        print("Error: google_api_key environment variable not set.")
        return None
    try:
        configure(api_key=api_key)
        return MedicalChatbot()  # Initialize the MedicalChatbot
    except Exception as e:
        print(f"Error initializing chatbot: {e}")
        return None

# Initialize bot globally
bot = initialize_bot()
if bot:
    print("Bot initialized successfully")
else:
    print("Bot initialization failed")

# Store user conversation contexts
user_contexts = {}

@app.route('/')
def index():
    if bot:
        session['language'] = 'en' # Default language
        session['user_id'] = str(uuid.uuid4())
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
    user_id = session.get('user_id', 'web_user')  # <-- replace this logic if you want more dynamic IDs
    message = request.form.get('message', '').strip()
    language = session.get('language', 'en')

    # Get the chatbot instance for this user
    chatbot = get_or_create_user_bot(user_id)

    if not chatbot:
        error_text = translate_text("Error: Chatbot not initialized", language)
        return jsonify({'response': {'text': error_text}})

    # Process the message using the user-specific chatbot
    bot_response = chatbot.process_message(message)

    # Try to parse a JSON-formatted response (with buttons)
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
    
    except (json.JSONDecodeError, TypeError):
        # If not JSON or response is plain text
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

            response = bot.process_message(message)

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

recent_messages = {}

@app.route('/gupshup_webhook', methods=['POST'])
def gupshup_webhook():
    try:
        data = request.get_json(force=True, silent=True)

        payload = data.get("payload", {}).get("payload", {})
        message = payload.get("text", "")
        user_phone = data.get("payload", {}).get("sender", {}).get("phone", "")  # This is the user

        if not user_phone or not message:
            return jsonify({"status": "error", "message": "Missing phone or message"}), 400

        # ✅ Prevent duplicate replies
        if recent_messages.get(user_phone) == message:
            return jsonify({"status": "duplicate_ignored"}), 200

        recent_messages[user_phone] = message

        # ✅ Use user_phone to maintain unique session
        chatbot = get_or_create_user_bot(user_phone)

        response = chatbot.process_message(message)

        if response:
            send_reply_to_gupshup(user_phone, response)
        return '', 200

    except Exception as e:
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
        print(f"Gupshup sent: {r.text}")
    except Exception as e:
        print(f"Failed to send message to Gupshup: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8585)