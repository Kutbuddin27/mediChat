from google.generativeai import GenerativeModel
from core_functionality import Database, ConversationState
import json
import os,requests

class PathologyBot:
    def __init__(self, api_key):
        self.model = GenerativeModel('gemini-1.5-flash')
        self.db = Database()
        self.state_manager = ConversationState()
        self.test_details = {
            'CBC': {'price': 800, 'prep': 'Fasting required'},
            'RBC': {'price': 400, 'prep': 'No preparation needed'}
        }

    def get_response(self, user_id, message):
        message_lower = message.strip().lower()
        start_keywords = ['hi', 'hello', 'start', 'menu', 'main menu', 'home','okay']
        # Allow overriding the state manually
        if message_lower in start_keywords: 
            self.state_manager.update_state(user_id, 'START')
            return self._handle_start(user_id)
        elif message_lower == 'book test':
            self.state_manager.update_state(user_id, 'BOOK_TEST')
            return self._handle_test_type(user_id, message)
        elif message_lower == 'select test':
            self.state_manager.update_state(user_id, 'SELECT_TEST')
            return self._handle_test_selection(user_id, message)
        elif message_lower == 'select slot':
            self.state_manager.update_state(user_id, 'SELECT_SLOT')
            return self._handle_slot_selection(user_id, message)
        elif message_lower == 'name':
            self.state_manager.update_state(user_id, 'GET_NAME')
            return self._handle_get_name(user_id, message)
        elif message_lower == 'phone':
            self.state_manager.update_state(user_id, 'GET_PHONE')
            return self._handle_get_phone(user_id, message)
        elif message_lower == 'confirm':
            self.state_manager.update_state(user_id, 'CONFIRM')
            return self._handle_confirmation(user_id, message)

        # Proceed with existing state if no manual override
        state = self.state_manager.get_state(user_id)
        current_state = state.get('current_state', 'START')

        if current_state == 'START':
            return self._handle_start(user_id)
        elif current_state == 'BOOK_TEST':
            return self._handle_test_type(user_id, message)
        elif current_state == 'SELECT_TEST':
            return self._handle_test_selection(user_id, message)
        elif current_state == 'SELECT_SLOT':
            return self._handle_slot_selection(user_id, message)
        elif current_state == 'GET_NAME':
            return self._handle_get_name(user_id, message)
        elif current_state == 'GET_PHONE':
            return self._handle_get_phone(user_id, message)
        elif current_state == 'CONFIRM':
            return self._handle_confirmation(user_id, message)
        else:
            return self._handle_main_menu(user_id, message)

    def _handle_start(self, user_id):
        self.state_manager.update_state(user_id, 'MAIN_MENU')
        return "Welcome to City Pathology! How can I help you today?\n" + self._main_menu_text()

    def _handle_main_menu(self, user_id, message):
        try:
            # Check if the message is a valid number (1 or 2)
            if int(message) == 1 or 'book test' in message.lower():
                return self._initiate_booking(user_id)
            elif 'view test' in message.lower() or int(message) == 2:
                return self._show_appointments(user_id)
        except ValueError:
            # If the message is not a number, process it with Google API
            if 'menu' not in message.lower():
                processed_message = self._process_with_google_api(message)
                return processed_message

        # If input is invalid, show the menu again
        return "Please choose a valid option:\n" + self._main_menu_text()

    def _initiate_booking(self, user_id):
        self.state_manager.update_state(user_id, 'BOOK_TEST')
        return json.dumps({
            'text': 'Select test category:',
            'buttons': [{'text': 'Blood Test', 'value': 'blood_test'}]
        })

    def _handle_test_type(self, user_id, message):
        self.state_manager.update_state(user_id, 'SELECT_TEST')
        return json.dumps({
            'text': 'Select test type:',
            'buttons': [{'text': 'CBC', 'value': 'CBC'}, {'text': 'RBC', 'value': 'RBC'}]
        })

    def _handle_test_selection(self, user_id, message):
        if message not in ['CBC', 'RBC']:
            return "Invalid selection. Please choose CBC or RBC"
        
        self.state_manager.update_state(user_id, 'SELECT_SLOT', test=message)
        slots = self.db.get_available_slots()
        return json.dumps({
            'text': 'Select time slot:',
            'buttons': [{'text': slot, 'value': slot} for slot in slots]
        })

    def _handle_slot_selection(self, user_id, message):
        self.state_manager.update_state(user_id, 'GET_NAME', slot=message)
        return "Please enter your full name:"

    def _handle_get_name(self, user_id, message):
        self.state_manager.update_state(user_id, 'GET_PHONE', name=message.strip())
        return "Please enter your phone number:"

    def _handle_get_phone(self, user_id, message):
        state = self.state_manager.get_state(user_id)
        details = {
            'test': state['context']['test'],
            'slot': state['context']['slot'],
            'name': state['context']['name'],
            'phone': message.strip()
        }
        self.state_manager.update_state(user_id, 'CONFIRM', **details)
        
        test_info = self.test_details[details['test']]
        return json.dumps({
            'text': f'''Confirm booking:
Test: {details['test']} (₹{test_info['price']})
Time: {details['slot']}
Name: {details['name']}
Phone: {details['phone']}
Preparation: {test_info['prep']}

Proceed with booking?''',
            'buttons': [{'text': 'Confirm', 'value': 'yes'}, {'text': 'Cancel', 'value': 'no'}]
        }) 

    def _handle_confirmation(self, user_id, message):
        state = self.state_manager.get_state(user_id)
        if message.lower() == 'yes':
            self.db.book_test(
            user_id,
            state['context']['test'],
            state['context']['slot'],
            state['context']['name'],
            state['context']['phone']
            )
            response = "Booking confirmed! 🎉\nAppointment ID: " + \
            f"{list(self.db.tests.keys())[-1]}\nType 'menu' for main menu"
        else:
            response = "Booking cancelled. Type 'menu' to start over"

        self.state_manager.update_state(user_id, 'MAIN_MENU')
        return response

    def _show_appointments(self, user_id):
        apps = self.db.tests
        user_apps = [a for a in apps.values() if a['user_id'] == user_id]
        if not user_apps:
            return "No appointments found. Type 'menu' to book one"
        
        return "\n".join(
            f"{a['test_name']} - {a['date_time']} ({a['status']})"
            for a in user_apps
        )

    def _main_menu_text(self):
        return ("Main Menu:\n1. Book Test\n2. View Appointments\n"
                "3. Test Prices\n4. Help")

    def _main_menu_response(self, user_id):
        self.state_manager.update_state(user_id, 'MAIN_MENU')
        return self._main_menu_text()
    def _process_with_google_api(self, message):
        url = "https://api.google.com/process"  # Replace with the actual Google API endpoint
        headers = {"Authorization": f"Bearer {os.getenv('google_api_key')}"}
        data = {"message": message}

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            return response.json().get("processed_message", "Error processing message.")
        else:
            return "Error communicating with Google API."
