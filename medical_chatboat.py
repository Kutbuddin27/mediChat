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
import re  

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
        print("Data  :",data)
        payload = data.get("payload", {}).get("payload", {})
        print("Payload  :",payload) 
        message = payload.get("text", "") or payload.get("title") or ""
        message = message.strip().lower()
        print("Message  :",message)
        user_phone = data.get("payload", {}).get("sender", {}).get("phone", "")  # This is the user
        if not user_phone or not message:
            return jsonify({"status": "error", "message": "Missing phone or message"}), 400
        # ✅ Prevent duplicate replies
        if recent_messages.get(user_phone) == message:
            return "", 200
        
        recent_messages[user_phone] = message
        print("recent messages: ",recent_messages)
        # ✅ Use user_phone to maintain unique session
        chatbot = get_or_create_user_bot(user_phone)
        response = chatbot.process_message(message)
        print("gupshup webhook :",response)
        if response:
            if "select a doctor" in response:
                send_button(phone=user_phone,
                body=response)
            elif "YYYY-MM-DD" in response:
                send_button(phone=user_phone,body=response)
            elif "following slots available" in response:
                send_button(phone=user_phone,body=response)
            else:
                send_reply_to_gupshup(
                    phone=user_phone,
                    body=response
                )
        return '', 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 🟢 Send Reply to Gupshup Function with Template Message
def send_reply_to_gupshup(phone, body):
    GUPSHUP_API_URL = "https://api.gupshup.io/wa/api/v1/msg"
    GUPSHUP_APP_NAME = os.getenv("gupshup_app_name")
    GUPSHUP_API_KEY = os.getenv("gupshup_api_key")
    GUPSHUP_SOURCE = os.getenv("gupshup_source")
    
    # Determine if the message contains button information
    try:
        # Check if body is a JSON string containing buttons
        message_data = json.loads(body)
        has_buttons = "buttons" in message_data
        message_text = message_data.get("text", "")
        buttons = message_data.get("buttons", [])
    except (json.JSONDecodeError, TypeError):
        # If it's not valid JSON, treat it as plain text
        has_buttons = False
        message_text = body
        buttons = []
    
    # Clean up any markdown artifacts
    message_text = message_text.replace("```", "").strip()
    
    if has_buttons:
        # For interactive buttons - this is the key change
        interactive_object = {
            "type": "button",
            "body": {
                "text": message_text
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"btn_{i}",
                            "title": btn["text"][:20]  # WhatsApp has a 20 char limit on button text
                        }
                    } for i, btn in enumerate(buttons[:3])  # WhatsApp allows max 3 buttons
                ]
            }
        }
        
        # The key difference: Don't nest this under another "message" property
        payload = {
            "channel": "whatsapp",
            "source": GUPSHUP_SOURCE,
            "destination": phone,
            "src.name": GUPSHUP_APP_NAME,
            "message": json.dumps({
                "type": "interactive",
                "interactive": interactive_object  # No need to serialize this again
            })
        }
    else:
        # For simple text messages
        payload = {
            "channel": "whatsapp",
            "source": GUPSHUP_SOURCE,
            "destination": phone,
            "src.name": GUPSHUP_APP_NAME,
            "message": json.dumps({
                "type": "text",
                "text": message_text
            })
        }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "apikey": GUPSHUP_API_KEY
    }

    try:
        # Debug what we're sending
        print(f"Sending to Gupshup: {json.dumps(payload)}")
        
        r = requests.post(GUPSHUP_API_URL, data=payload, headers=headers)
        print(f"Gupshup response status: {r.status_code}")
        print(f"Gupshup response: {r.text}")
        return r
    except Exception as e:
        print(f"Failed to send message to Gupshup: {e}")
        return None

def send_button(phone,body):
    url = "https://api.gupshup.io/wa/api/v1/msg"
    message = ''
    if "YYYY-MM-DD" in body:
        dates = re.findall(r'\d{4}-\d{2}-\d{2}', body)
        message = "{\"type\":\"quick_reply\",\"msgid\":\"qr1\",\"content\":{\"type\":\"text\",\"header\":\"Okay! We have the following dates available:\",\"text\":\"Please select a date by typing the corresponding option.\"},\"options\":[{\"type\":\"text\",\"title\":\"%s\"},{\"type\":\"text\",\"title\":\"%s\"},{\"type\":\"text\",\"title\":\"%s\"}]}" % (dates[0],dates[1],dates[2])
    elif "select a doctor" in body:
        message = "{\"type\":\"quick_reply\",\"msgid\":\"qr1\",\"content\":{\"type\":\"text\",\"header\":\"Okay! We have the following doctors available:\",\"text\":\"Please select a doctor by typing the corresponding letter.\"},\"options\":[{\"type\":\"text\",\"title\":\"Dr. Batra\"},{\"type\":\"text\",\"title\":\"Dr. Shah\"},{\"type\":\"text\",\"title\":\"Dr. Momin\"}]}"
    elif "the following slots available" in body:
        message = "{\"type\":\"quick_reply\",\"msgid\":\"qr1\",\"content\":{\"type\":\"text\",\"header\":\"Okay! We have the following doctors available:\",\"text\":\"Please select a doctor by typing the corresponding letter.\"},\"options\":[{\"type\":\"text\",\"title\":\"10:00 AM\"},{\"type\":\"text\",\"title\":\"11:00 AM\"},{\"type\":\"text\",\"title\":\"12:00 PM\"}]}"        
    payload = {
        "message": message,
        "channel": "whatsapp",
        "source": os.getenv("gupshup_source"),
        "destination": "919725193559",
        "src.name": os.getenv("gupshup_app_name")
    }
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "apikey": os.getenv("gupshup_api_key")
    }

    response = requests.post(url, data=payload, headers=headers)
    print(f"Gupshup response: {r.text}")
    return r

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8585)