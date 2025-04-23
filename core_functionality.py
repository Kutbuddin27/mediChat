import json
import uuid
import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

class Database:
    def __init__(self):
        self.tests = {}
        self.appointments = {}
        self.reports = {}
        self.users = {}
        
        # Connect to Google Sheets
        self.connect_to_sheets()
        # Load data from sheets
        self.load_from_sheets()

    def connect_to_sheets(self):
        """Connect to Google Sheets using service account credentials"""
        # Define the scope
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Load credentials from service account file
        # You'll need to create this JSON file from Google Cloud Console
        credentials = Credentials.from_service_account_file(
            'medichat-457610-72b7fae1ad7e.json', 
            scopes=SCOPES
        )
        
        # Authorize with Google
        self.client = gspread.authorize(credentials)
        
        # Open the Google Spreadsheet (by title or by URL)
        # Replace 'Pathology Database' with your actual spreadsheet name
        try:
            self.spreadsheet = self.client.open('Pathology Database')
            #self.spreadsheet.share('kapadiakutbuddin@gmail.com', perm_type='user', role='writer')
        except gspread.exceptions.SpreadsheetNotFound:
            # Create a new spreadsheet if it doesn't exist
            self.spreadsheet = self.client.create('Pathology Database')
            self.spreadsheet.share('kapadiakutbuddin@gmail.com', perm_type='user', role='writer')
            
            # Create necessary worksheets
            self.spreadsheet.add_worksheet(title="tests", rows=1000, cols=20)
            self.spreadsheet.add_worksheet(title="appointments", rows=1000, cols=20)
            self.spreadsheet.add_worksheet(title="reports", rows=1000, cols=20)
            self.spreadsheet.add_worksheet(title="users", rows=1000, cols=20)
            
            # Delete the default Sheet1 that gets created
            default_sheet = self.spreadsheet.worksheet("Sheet1")
            self.spreadsheet.del_worksheet(default_sheet)
            
            # Initialize headers for each worksheet
            tests_sheet = self.spreadsheet.worksheet("tests")
            tests_sheet.append_row([
                "test_id", "user_id", "test_name", "date_time", 
                "status", "user_name", "phone", "booking_time"
            ])
            
            users_sheet = self.spreadsheet.worksheet("users")
            users_sheet.append_row([
                "user_id", "name", "phone", "last_updated"
            ])
            
            # Similar headers for other sheets as needed
    
    def load_from_sheets(self):
        """Load data from Google Sheets into memory"""
        # Load tests
        try:
            tests_sheet = self.spreadsheet.worksheet("tests")
            all_tests = tests_sheet.get_all_records()
            
            for test in all_tests:
                test_id = test.get('test_id')
                if test_id:  # Skip header row and empty rows
                    self.tests[test_id] = {
                        'user_id': test.get('user_id'),
                        'test_name': test.get('test_name'),
                        'date_time': test.get('date_time'),
                        'status': test.get('status'),
                        'user_name': test.get('user_name'),
                        'phone': test.get('phone'),
                        'booking_time': test.get('booking_time')
                    }
            print(f"Spreadsheet URL: {self.spreadsheet.url}")
            print(f"Spreadsheet ID: {self.spreadsheet.id}")
            print(f"Owned by: {self.spreadsheet.owner().get('emailAddress')}")
            # Load users
            users_sheet = self.spreadsheet.worksheet("users")
            all_users = users_sheet.get_all_records()
            
            for user in all_users:
                user_id = user.get('user_id')
                if user_id:  # Skip header row and empty rows
                    self.users[user_id] = {
                        'name': user.get('name'),
                        'phone': user.get('phone'),
                        'last_updated': user.get('last_updated')
                    }
                    
            # Similarly load other data types (appointments, reports) as needed
        
        except Exception as e:
            print(f"Error loading data from sheets: {e}")
            # Initialize with empty dicts if there's an issue

    def save(self):
        """Update the Google Sheets with current data"""
        # Update tests sheet
        try:
            tests_sheet = self.spreadsheet.worksheet("tests")
            
            # Clear existing data (keeping headers)
            rows = tests_sheet.row_count
            if rows > 1:  # Keep the header row
                tests_sheet.delete_rows(2, rows)
            
            # Add all tests data
            for test_id, test_data in self.tests.items():
                tests_sheet.append_row([
                    test_id,
                    test_data.get('user_id', ''),
                    test_data.get('test_name', ''),
                    test_data.get('date_time', ''),
                    test_data.get('status', ''),
                    test_data.get('user_name', ''),
                    test_data.get('phone', ''),
                    test_data.get('booking_time', '')
                ])
            
            # Update users sheet
            users_sheet = self.spreadsheet.worksheet("users")
            
            # Clear existing data (keeping headers)
            rows = users_sheet.row_count
            if rows > 1:  # Keep the header row
                users_sheet.delete_rows(2, rows)
            
            # Add all users data
            for user_id, user_data in self.users.items():
                users_sheet.append_row([
                    user_id,
                    user_data.get('name', ''),
                    user_data.get('phone', ''),
                    user_data.get('last_updated', '')
                ])
                
            # Similarly update other sheets (appointments, reports) as needed
                
        except Exception as e:
            print(f"Error saving data to sheets: {e}")
            # As a fallback, save to JSON if Google Sheets fails
            with open('pathology_db_backup.json', 'w') as f:
                json.dump({
                    'tests': self.tests,
                    'appointments': self.appointments,
                    'reports': self.reports,
                    'users': self.users
                }, f, indent=2)

    def book_test(self, user_id, test_name, date_time, user_name=None, phone=None):
        test_id = f"APT{uuid.uuid4().hex[:6].upper()}"
        self.tests[test_id] = {
            'user_id': user_id,
            'test_name': test_name,
            'date_time': date_time,
            'status': 'booked',
            'user_name': user_name,
            'phone': phone,
            'booking_time': datetime.datetime.now().isoformat()
        }
        
        # Add the new test directly to the Google Sheet
        try:
            tests_sheet = self.spreadsheet.worksheet("tests")
            tests_sheet.append_row([
                test_id,
                user_id,
                test_name,
                date_time,
                'booked',
                user_name or '',
                phone or '',
                datetime.datetime.now().isoformat()
            ])
        except Exception as e:
            print(f"Error adding test to sheet: {e}")
            # Continue with the in-memory update and call save() as a fallback
            self.save()
            
        return test_id

    def get_available_slots(self):
        now = datetime.datetime.now()
        start_time,end_time = 0,0
        # Determine start and end based on time
        if now.hour >= 18:
            # If past 6 PM, show tomorrow's slots from 9 to 18
            start_time = now + datetime.timedelta(days=1)
            start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
            end_time = start_time.replace(hour=18, minute=0, second=0, microsecond=0)
        else:
            # Otherwise, show today's slots from next hour to 18:00
            start_time = now + datetime.timedelta(hours=1)
            start_time = start_time.replace(minute=0, second=0, microsecond=0)

            # If next hour is past 6 PM, go to tomorrow
            if start_time.hour >= 18:
                start_time = now + datetime.timedelta(days=1)
                start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
                end_time = start_time.replace(hour=18, minute=0, second=0, microsecond=0)
            else:
                end_time = now.replace(hour=18, minute=0, second=0, microsecond=0)

        # Generate time slots
        slots = []
        current = start_time
        print(start_time,end_time)
        while current <= end_time:
            slots.append(current.strftime("%d-%m-%Y %H:%M"))
            current += datetime.timedelta(hours=1)
        return slots

    def save_user_info(self, user_id, name, phone):
        self.users[user_id] = {
            'name': name,
            'phone': phone,
            'last_updated': datetime.datetime.now().isoformat()
        }
        
        # Add/update the user directly to the Google Sheet
        try:
            users_sheet = self.spreadsheet.worksheet("users")
            
            # Check if user already exists in sheet
            user_row = None
            try:
                cell = users_sheet.find(user_id)
                if cell:
                    user_row = cell.row
            except:
                pass
                
            if user_row:
                # Update existing user
                users_sheet.update(f'B{user_row}', name)
                users_sheet.update(f'C{user_row}', phone)
                users_sheet.update(f'D{user_row}', datetime.datetime.now().isoformat())
            else:
                # Add new user
                users_sheet.append_row([
                    user_id,
                    name,
                    phone,
                    datetime.datetime.now().isoformat()
                ])
        except Exception as e:
            print(f"Error saving user to sheet: {e}")
            # Call save() as a fallback
            self.save()

class ConversationState:
    # No changes needed to this class
    def __init__(self):
        self.states = {}

    def get_state(self, user_id):
        if user_id not in self.states:
            self.states[user_id] = {
                'current_state': 'START',
                'language': 'English',
                'context': {},
                'last_buttons': []
            }
        return self.states[user_id]

    def update_state(self, user_id, new_state, **kwargs):
        state = self.get_state(user_id)
        state['current_state'] = new_state
        state['context'].update(kwargs)
        return state

    def store_buttons(self, user_id, buttons):
        state = self.get_state(user_id)
        state['last_buttons'] = buttons
        return state

    def get_button_by_value(self, user_id, value):
        state = self.get_state(user_id)
        return next((b for b in state['last_buttons'] if b['value'] == value), None)
