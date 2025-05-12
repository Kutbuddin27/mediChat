from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
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
from functools import wraps
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24) # Required for using session

translator =    GoogleTranslator()
ADMIN_USERNAME = os.getenv("admin_username")  # Set this in your .env file
ADMIN_PASSWORD = os.getenv("admin_password")  # Change this to a strong password

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
# Admin login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session or not session['admin_logged_in']:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

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
# Admin Routes
@app.route('/admin')
@login_required
def admin_dashboard():
    try:
        sample_chatbot = get_or_create_user_bot("admin")
        if not sample_chatbot or not hasattr(sample_chatbot, 'database'):
            return "Error: Cannot access database"
        
        db = sample_chatbot.database
        patients = db.data["patients"]
        appointments = db.data["appointments"]
        doctors = db.data["doctors"]

        # Filter appointments to show only today's or future appointments
        today = datetime.today().date()

        upcoming_appointments = {}
        for apt_id, apt_data in appointments.items():
            try:
                apt_date = datetime.strptime(apt_data['date'], '%Y-%m-%d').date()
                if apt_date >= today:
                    upcoming_appointments[apt_id] = apt_data
            except Exception as e:
                print(f"Error parsing appointment date for {apt_id}: {e}")

        return render_template('admin_dashboard.html', 
                            patients=patients, 
                            appointments=upcoming_appointments,
                            doctors=doctors)
    except Exception as e:
        return f"Error accessing database: {str(e)}"

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/patients')
@login_required
def admin_patients():
    try:
        sample_chatbot = get_or_create_user_bot("admin")
        db = sample_chatbot.database
        patients = db.data["patients"]
        return render_template('admin_patients.html', patients=patients)
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/admin/appointments')
@login_required
def admin_appointments():
    try:
        sample_chatbot = get_or_create_user_bot("admin")
        db = sample_chatbot.database
        appointments = db.data["appointments"]
        patients = db.data["patients"]
        doctors = db.data["doctors"]

        # Get today's date
        today = datetime.today().date()

        # Filter appointments: keep only those with date >= today
        upcoming_appointments = {}
        for apt_id, apt_data in appointments.items():
            try:
                apt_date = datetime.strptime(apt_data['date'], '%Y-%m-%d').date()
                if apt_date >= today:
                    upcoming_appointments[apt_id] = apt_data
            except Exception as e:
                print(f"Error parsing appointment date for {apt_id}: {e}")

        return render_template('admin_appointments.html', 
                                appointments=upcoming_appointments,
                                patients=patients,
                                doctors=doctors)
    except Exception as e:
        return f"Error: {str(e)}"
        
@app.route('/admin/edit_appointment/<appointment_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_appointment(appointment_id):
    try:
        sample_chatbot = get_or_create_user_bot("admin")
        db = sample_chatbot.database
        appointment = db.get_appointment(appointment_id)
        patients = db.data["patients"]
        doctors = db.data["doctors"]

        if request.method == 'POST':
            updated_data = {
                "patient_id": request.form.get('patient_id', ''),
                "doctor_id": request.form.get('doctor_id', ''),
                "date": request.form.get('date', ''),
                "time": request.form.get('time', ''),
                "reason": request.form.get('reason', ''),
                "status": request.form.get('status', 'scheduled')
            }
            db.update_appointment(appointment_id, updated_data)
            flash('Appointment updated successfully')
            return redirect(url_for('admin_appointments'))

        return render_template('admin_edit_appointment.html',
                            appointment_id=appointment_id,
                            appointment=appointment,
                            patients=patients,
                            doctors=doctors)
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('admin_appointments'))
@app.route('/admin/delete_appointment/<appointment_id>', methods=['POST'])
@login_required
def admin_delete_appointment(appointment_id):
    try:
        sample_chatbot = get_or_create_user_bot("admin")
        db = sample_chatbot.database
        db.delete_appointment(appointment_id)
        flash('Appointment deleted successfully')
    except Exception as e:
        flash(f"Error deleting appointment: {str(e)}")
    return redirect(url_for('admin_appointments'))

@app.route('/admin/doctors')
@login_required
def admin_doctors():
    try:
        sample_chatbot = get_or_create_user_bot("admin")
        db = sample_chatbot.database
        doctors = db.data["doctors"]
        return render_template('admin_doctors.html', doctors=doctors)
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/admin/add_patient', methods=['GET', 'POST'])
@login_required
def admin_add_patient():
    if request.method == 'POST':
        try:
            sample_chatbot = get_or_create_user_bot("admin")
            db = sample_chatbot.database
            
            # Generate a unique ID for the patient
            patient_id = f"p_{uuid.uuid4().hex[:8]}"
            
            # Gather patient data from form
            patient_data = {
                "name": request.form.get('name', ''),
                "age": request.form.get('age', ''),
                "gender": request.form.get('gender', ''),
                "phone": request.form.get('phone', ''),
                "email": request.form.get('email', ''),
                "address": request.form.get('address', ''),
                "medical_history": request.form.get('medical_history', '')
            }
            
            # Add patient to database
            success = db.add_patient(patient_id, patient_data)
            
            if success:
                flash('Patient added successfully')
                return redirect(url_for('admin_patients'))
            else:
                flash('Failed to add patient')
                
        except Exception as e:
            flash(f'Error: {str(e)}')
    
    return render_template('admin_add_patient.html')

@app.route('/admin/add_appointment', methods=['GET', 'POST'])
@login_required
def admin_add_appointment():
    try:
        sample_chatbot = get_or_create_user_bot("admin")
        db = sample_chatbot.database
        patients = db.data["patients"]
        doctors = db.data["doctors"]
        
        if request.method == 'POST':
            # Generate a unique ID for the appointment
            appointment_id = f"apt_{uuid.uuid4().hex[:8]}"
            
            # Gather appointment data from form
            appointment_data = {
                "patient_id": request.form.get('patient_id', ''),
                "doctor_id": request.form.get('doctor_id', ''),
                "date": request.form.get('date', ''),
                "time": request.form.get('time', ''),
                "reason": request.form.get('reason', ''),
                "status": "scheduled"
            }
            
            # Book appointment in database
            success = db.book_appointment(appointment_id, appointment_data)
            
            if success:
                flash('Appointment booked successfully')
                return redirect(url_for('admin_appointments'))
            else:
                flash('Failed to book appointment')
        
        return render_template('admin_add_appointment.html', 
                            patients=patients,
                            doctors=doctors)
    
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/admin/edit_patient/<patient_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_patient(patient_id):
    try:
        sample_chatbot = get_or_create_user_bot("admin")
        db = sample_chatbot.database
        
        if request.method == 'POST':
            # Gather updated patient data from form
            patient_data = {
                "name": request.form.get('name', ''),
                "age": request.form.get('age', ''),
                "gender": request.form.get('gender', ''),
                "phone": request.form.get('phone', ''),
                "email": request.form.get('email', ''),
                "address": request.form.get('address', ''),
                "medical_history": request.form.get('medical_history', '')
            }
            # Update patient in database
            db.add_patient(patient_id, patient_data)  # The add_patient method updates if patient exists
            flash('Patient updated successfully')
            return redirect(url_for('admin_patients'))
        
        # Get current patient data for edit form
        patient_data = db.get_patient(patient_id)
        return render_template('admin_edit_patient.html', 
                            patient_id=patient_id,
                            patient=patient_data)
    
    except Exception as e:
        flash(f'Error: {str(e)}')
        return redirect(url_for('admin_patients'))

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
gupshup_logger.addHandler(gupshup_file_handler)

# Define common greeting patterns
GREETING_PATTERNS = [
    r'\b(?:hi|hii|hiii|hello|hey|howdy|greetings|namaste|good\s*(?:morning|afternoon|evening|day)|hola)\b',
    r'\bstart\b',
    r'\bmenu\b',
    r'\bhelp\b'
]

recent_messages = {}
@app.route('/gupshup_webhook', methods=['POST'])
def gupshup_webhook():
    try:
        data = request.get_json(force=True, silent=True)
        #print("Data  :",data)
        payload = data.get("payload", {}).get("payload", {})
        #print("Payload  :",payload) 
        message = payload.get("text", "") or payload.get("title") or ""
        message = message.strip().lower()
        #print("Message  :",message)
        user_phone = data.get("payload", {}).get("sender", {}).get("phone", "")  # This is the user
        if not user_phone or not message:
            return jsonify({"status": "error", "message": "Missing phone or message"}), 400
        
        # ✅ Prevent duplicate replies
        if recent_messages.get(user_phone) == message:
            return "", 200
        
        print("User------>",user_phone)
        recent_messages[user_phone] = message
        
        # Check if the message is a greeting
        is_greeting = any(re.search(pattern, message, re.IGNORECASE) for pattern in GREETING_PATTERNS)
        
        # If greeting is detected, send the global menu
        if is_greeting:
            send_global_menu(user_phone)
            return '', 200
        
        # If not a greeting, proceed with normal flow
        # ✅ Use user_phone to maintain unique session
        chatbot = get_or_create_user_bot(user_phone)
        response = chatbot.process_message(message, user_phone)
        
        # print("gupshup webhook :",response)
        if response:
            if "select a doctor" in response:
                send_button(phone=user_phone, body=response)
            elif "Y-M-D" in response:
                send_button(phone=user_phone, body=response)
            elif re.search(r"morning\s+or\s+evening\s+slot", response, re.IGNORECASE):
                send_button(phone=user_phone, body=response)
            elif "What time works for you?" in response:
                send_button(phone=user_phone, body=response)
            else:
                send_reply_to_gupshup(
                    phone=user_phone,
                    body=response
                )
        return '', 200
    except Exception as e:
        gupshup_logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def send_global_menu(phone):
    """
    Send a global menu with options for the user to interact with
    """
    url = "https://api.gupshup.io/wa/api/v1/msg"
    
    payload = {
        "message": json.dumps({
            "type": "list",
            "title": "🏥 Welcome to Apple Hospital",
            "body": """
                I'm your dedicated Medical Assistant, here to help you with all your healthcare needs. I can assist you with:

            • Booking appointments with our specialists
            • Providing information about medical procedures
            • Answering general health questions
            • Managing your patient information

                How may I assist you today? If you're looking to schedule an appointment or have medical queries, I'm here to help!
                """,
            "msgid": "list1",
            "globalButtons": [{
                "type": "text",
                "title": "Menu"
            }],
            "items": [{
                "title": "Available Services",
                "subtitle": "How can we help you today?",
                "options": [
                    {
                        "type": "text",
                        "title": "Book an Appointment",
                        "description": "Book an appointment if you need a consultation with our doctors",
                        "postbackText": "book appointment"
                    },
                    {
                        "type": "text",
                        "title": "View my Appointments",
                        "description": "See your currently booked appointments",
                        "postbackText": "view appointments"
                    },
                    {
                        "type": "text",
                        "title": "Cancel Appointment",
                        "description": "Cancel an existing appointment",
                        "postbackText": "cancel appointment"
                    },
                    {
                        "type": "text",
                        "title": "Reschedule Appointments",
                        "description": "Reschedule an existing appointment",
                        "postbackText": "reschedule appointment"
                    },
                    {
                        "type": "text",
                        "title": "Other Medical Info",
                        "description": "Learn about medical procedures and services",
                        "postbackText": "medical info"
                    },
                    {
                        "type": "text",
                        "title": "New Patient",
                        "description": "Store patient information for new patients",
                        "postbackText": "new patient"
                    }
                ]
            }]
        }),
        "channel": "whatsapp",
        "source": os.getenv("gupshup_source"),
        "destination": phone,
        "src.name": os.getenv("gupshup_app_name")
    }
    
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "apikey": os.getenv("gupshup_api_key")
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        print(f"Global menu response: {response.text}")
        gupshup_logger.info(f"Sent global menu to {phone}. Response: {response.status_code}")
        return response
    except Exception as e:
        gupshup_logger.error(f"Failed to send global menu: {e}")
        print(f"Failed to send global menu: {e}")
        return None

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

def send_button(phone, body):
    url = "https://api.gupshup.io/wa/api/v1/msg"
    message = ''
    print("send_button---->", body)
    
    # For date selection
    if "Y-M-D" in body or re.search(r'\b[A-Z]\.\s+\w+,\s+\w+\s+\d+,\s+\d{4}\s+\(\d{4}-\d{2}-\d{2}\)', body):
        # Extract all dates in YYYY-MM-DD format
        dates = re.findall(r'\d{4}-\d{2}-\d{2}', body)
        
        # Create options dynamically for all available dates
        options = []
        for date in dates:
            options.append({"type": "text", "title": date})
        
        # Create the message JSON with dynamic options
        message_data = {
            "type": "quick_reply",
            "msgid": "qr1",
            "content": {
                "type": "text",
                "header": "Okay! We have the following dates available:",
                "text": "Please select a date by typing the corresponding option."
            },
            "options": options
        }
        message = json.dumps(message_data)
    
    # For morning/evening selection
    elif re.search(r'morning\s+or\s+evening\s+slot', body, re.IGNORECASE):
        day = re.search(r'\d{4}-\d{2}-\d{2}', body)
        
        # Create options based on what's mentioned in the message
        options = []
        if "morning" in body.lower():
            options.append({"type": "text", "title": "Morning"})
        if "evening" in body.lower():
            options.append({"type": "text", "title": "Evening"})
            
        message_data = {
            "type": "quick_reply",
            "msgid": "qr1",
            "content": {
                "type": "text",
                "header": f"Select daytime on {day.group()}:",
                "text": "Please select your preferred time of day."
            },
            "options": options
        }
        message = json.dumps(message_data)
    
    # For doctor selection
    elif "select a doctor" in body.lower():
        # Extract all doctors with their specialties
        doctor_entries = re.findall(r'[A-Z]\.\s+(Dr\.\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+\([A-Za-z\s\-]+\))', body)
        
        if not doctor_entries:
            # Alternative pattern if the first one doesn't match
            doctor_entries = re.findall(r'[A-Z]\.\s+(.*?)(?:\n|$)', body)
        
        # Try to extract specialization
        specialization_match = re.search(r"You've selected ([A-Za-z\s\-]+)\.", body)
        specialization = specialization_match.group(1) if specialization_match else "Specialist"
        
        # Create options for each available doctor
        options = []
        for entry in doctor_entries:
            # Extract just the doctor name (without the letter option)
            doctor_name = entry.strip()
            options.append({"type": "text", "title": doctor_name[:20]})  # Limit to 20 chars for button
        
        message_data = {
            "type": "quick_reply",
            "msgid": "qr1",
            "content": {
                "type": "text",
                "header": f"Great! Select a doctor in {specialization}:",
                "text": "Select the doctor you prefer"
            },
            "options": options
        }
        message = json.dumps(message_data)
    
    # For time slot selection
    elif "What time works for you?" in body:
        # Extract all available time slots
        times = re.findall(r'\b\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}\s*[APap][Mm]\b', body)

        # Create options for each available time
        options = []
        for time in times:
            options.append({"type": "text", "title": time})
        
        message_data = {
            "type": "quick_reply",
            "msgid": "qr1",
            "content": {
                "type": "text",
                "header": "Okay! We have the following times available:",
                "text": "Please select a time by typing the corresponding option."
            },
            "options": options
        }
        message = json.dumps(message_data)
    
    # If no pattern matches, don't send a button message
    if not message:
        print("No button pattern matched for message body")
        return None
    
    payload = {
        "message": message,
        "channel": "whatsapp",
        "source": os.getenv("gupshup_source"),
        "destination": phone,
        "src.name": os.getenv("gupshup_app_name")
    }
    
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "apikey": os.getenv("gupshup_api_key")
    } 
    response = requests.post(url, data=payload, headers=headers)
    print(f"Gupshup response: {response.text}")
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8585)