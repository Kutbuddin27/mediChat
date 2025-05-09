# Medical Chatbot with LangChain using Google Generative AI
# Features: Document Handling, Prompt Management, Memory, Integrations

import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import re
# Load environment variables from .env file
load_dotenv()

# LangChain imports with updated import paths
from langchain_community.embeddings import HuggingFaceEmbeddings  # Use HuggingFace instead of Google Palm
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI  # For Gemini chat
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate,ChatPromptTemplate
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType

# Access the Gemini API key from environment variables
GOOGLE_API_KEY = os.getenv("google_api_key")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set in .env file")

# ---- Document Handling ----
class MedicalDocumentHandler:
    def __init__(self, docs_path: str = "medical_docs"):
        self.docs_path = docs_path
        # Use HuggingFace embeddings instead of Google Palm which is having compatibility issues
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.vector_store = None
        self.initialize_docs()
        
    def initialize_docs(self):
        """Load medical documents and create a searchable vector store"""
        if not os.path.exists(self.docs_path):
            os.makedirs(self.docs_path)
            # Create a sample medical document if none exists
            with open(f"{self.docs_path}/sample_procedures.txt", "w") as f:
                f.write("""
                Annual Physical Examination: A comprehensive health check performed yearly.
                Vaccination: Preventive treatment to develop immunity against specific diseases.
                Blood Test: Analysis of blood samples to detect medical conditions.
                X-Ray: Imaging technique using electromagnetic radiation to view internal structures.
                MRI Scan: Magnetic resonance imaging to create detailed images of organs and tissues.
                CT Scan: Computed tomography scan for detailed internal images.
                Ultrasound: Using sound waves to produce images of structures within the body.
                ECG: An ECG, or electrocardiogram, is a medical test that records the electrical activity of the heart. It's a simple, non-invasive way to assess heart function, primarily by measuring heart rate and rhythm. The ECG can help diagnose various heart conditions, including arrhythmias, heart attacks, and other abnormalities. 
                You are a helpful and informative medical assistant for Apple Hospital. Provide accurate, 
                evidence-based medical information in response to user queries. Keep responses concise but 
                thorough. Always clarify that you're providing general information, not medical advice, and 
                recommend consulting healthcare professionals for personalized care.

                For questions about symptoms, treatments, or conditions, provide general educational information.
                For questions about medications, provide general information about uses, common side effects, 
                and important warnings.

                Never make specific diagnoses or treatment recommendations for individuals. Always maintain a 
                professional, supportive tone.
                """)
        
        # Load documents
        documents = []
        for file in os.listdir(self.docs_path):
            if file.endswith(".txt"):
                loader = TextLoader(f"{self.docs_path}/{file}")
                documents.extend(loader.load())
        
        # Split documents into chunks
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
        texts = text_splitter.split_documents(documents)
        
        # Create vector store
        self.vector_store = FAISS.from_documents(texts, self.embeddings)
        print(f"Loaded {len(texts)} document chunks into vector store")
    
    def search_docs(self, query: str, k: int = 3) -> List[str]:
        """Search the vector store for relevant document chunks"""
        if not self.vector_store:
            return ["No documents available"]
        
        docs = self.vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]

# ---- Prompt Management ----
class MedicalPromptManager:
    def __init__(self):
        self.prompts = {
            "greeting": PromptTemplate(
                input_variables=[],
                template="""
                🏥 *Welcome to Apple Hospital* 🏥

                I'm your dedicated Medical Assistant, here to help you with all your healthcare needs. I can assist you with:

                • Booking appointments with our specialists
                • Providing information about medical procedures
                • Answering general health questions
                • Managing your patient information

                How may I assist you today? If you're looking to schedule an appointment or have medical queries, I'm here to help!
                """
            ),
            "booking": PromptTemplate(
                input_variables=["available_slots"],
                template="I'd be happy to help you book an appointment. Here are the available slots: {available_slots}. Which one would you prefer?"
            ),
            "medical_query": PromptTemplate(
                input_variables=["query", "context"],
                template="Medical Query: {query}\nRelevant Medical Information: {context}\nPlease provide a helpful response based on this information:"
            ),
            "patient_info": PromptTemplate(
                input_variables=["patient_name"],
                template="I need to collect some information for {patient_name}. Could you please provide your date of birth and reason for visit?"
            )
        }
    
    def get_prompt(self, prompt_type: str, **kwargs) -> str:
        """Get a formatted prompt of the specified type"""
        if prompt_type not in self.prompts:
            return f"Error: Prompt type '{prompt_type}' not found"
        
        return self.prompts[prompt_type].format(**kwargs)

# ---- Database Integration ----
class MedicalDatabase:
    def __init__(self, credentials_path="medichat-457610-72b7fae1ad7e.json"):
        """Initialize database with Google Sheets connection"""
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        
        # Use credentials to create a client to interact with Google Drive API
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
        client = gspread.authorize(credentials)
        
        # Open the spreadsheet (create if it doesn't exist)
        try:
            self.spreadsheet = client.open("PathologyDatabase")
            print(f"Spreadsheet URL: {self.spreadsheet.url}")
            print(f"Spreadsheet ID: {self.spreadsheet.id}")
        except gspread.SpreadsheetNotFound:
            self.spreadsheet = client.create("PathologyDatabase")
            
            # Create necessary worksheets
            self.spreadsheet.add_worksheet(title="patients", rows=1000, cols=20)
            self.spreadsheet.add_worksheet(title="appointments", rows=1000, cols=20)
            self.spreadsheet.add_worksheet(title="doctors", rows=100, cols=10)
            
            # Initialize doctors worksheet with sample data
            doctors_sheet = self.spreadsheet.worksheet("doctors")
            doctors_sheet.append_row(["id", "name", "specialty"])
            doctors_sheet.append_row(["dr_batra", "Dr. Batra", "General Practice"])
            doctors_sheet.append_row(["dr_shah", "Dr. Shah", "Cardiology"])
            doctors_sheet.append_row(["dr_momin", "Dr. Momin", "Pediatrics"])
            self.spreadsheet.share('kapadiakutbuddin@gmail.com', perm_type='user', role='writer')
        # Store worksheets
        self.patients_sheet = self.spreadsheet.worksheet("patients")
        self.appointments_sheet = self.spreadsheet.worksheet("appointments")
        self.doctors_sheet = self.spreadsheet.worksheet("doctors")
        
        # Cache data for faster access
        self.data = self._load_db()
    
    def _load_db(self) -> Dict:
        """Load data from Google Sheets"""
        # Initialize data structure
        data = {"patients": {}, "appointments": {}, "doctors": {}}
        
        # Load doctors
        doctors_data = self.doctors_sheet.get_all_records()
        for doctor in doctors_data:
            if "id" in doctor and doctor["id"]:
                doctor_id = doctor["id"]
                data["doctors"][doctor_id] = {
                    "name": doctor.get("name", ""),
                    "specialty": doctor.get("specialty", "")
                }
        
        # Load patients
        patients_data = self.patients_sheet.get_all_records()
        for patient in patients_data:
            if "id" in patient and patient["id"]:
                patient_id = patient["id"]
                data["patients"][patient_id] = {k: v for k, v in patient.items() if k != "id"}
        
        # Load appointments
        appointments_data = self.appointments_sheet.get_all_records()
        for appointment in appointments_data:
            if "id" in appointment and appointment["id"]:
                appointment_id = appointment["id"]
                data["appointments"][appointment_id] = {k: v for k, v in appointment.items() if k != "id"}
        
        return data
    
    def _save_db(self, data=None):
        """Save specific data to Google Sheets (not typically needed as we update directly)"""
        # This is a placeholder - we typically update the sheets directly in each method
        pass
    
    def add_patient(self, patient_id: str, patient_data: Dict) -> bool:
        """Add a new patient to the database"""
        # Update in-memory cache
        self.data["patients"][patient_id] = patient_data

        # Update Google Sheet
        # First check if patient already exists
        patient_ids = self.patients_sheet.col_values(1)
        if patient_id in patient_ids:
            # Update existing row
            row_idx = patient_ids.index(patient_id) + 1
            existing_headers = self.patients_sheet.row_values(1)

            # Update each cell
            for key, value in patient_data.items():
                if key in existing_headers:
                    col_idx = existing_headers.index(key) + 1
                    self.patients_sheet.update_cell(row_idx, col_idx, value)
        else:
            # Add new row
            # First ensure we have all necessary columns
            headers = self.patients_sheet.row_values(1)
            if not headers:
                # Add headers if sheet is empty
                headers = ["id"] + list(patient_data.keys())
                self.patients_sheet.append_row(headers)
            else:
                # Add any missing columns
                for key in patient_data:
                    if key not in headers:
                        headers.append(key)
                        self.patients_sheet.update_cell(1, len(headers), key)

            # Now add the data row
            row = [patient_id]
            for header in headers[1:]:  # Skip the ID column
                row.append(patient_data.get(header, ""))
            self.patients_sheet.append_row(row)

        return True
    def find_patient_id(self, name: str, phone: str) -> str:
        """Find patient ID based on name and phone number"""
        for pid, pdata in self.data["patients"].items():
            if pdata.get("name") == name and pdata.get("phone") == phone:
                return pid
        return ""

    def get_patient(self, patient_id: str) -> Dict:
        """Get patient information"""
        return self.data["patients"].get(patient_id, {})
    
    def book_appointment(self, appointment_id: str, appointment_data: Dict) -> bool:
        """Book an appointment with improved error handling and validation"""
        try:
            if not appointment_id or not appointment_data:
                print(f"ERROR: Invalid appointment data: id={appointment_id}, data={appointment_data}")
                return False
                
            if appointment_id in self.data["appointments"]:
                print(f"ERROR: Appointment ID {appointment_id} already exists")
                return False
            
            # First update in-memory cache
            self.data["appointments"][appointment_id] = appointment_data
            
            # Then update Google Sheet
            print(f"Saving appointment {appointment_id} to Google Sheet")
            
            # Check for headers
            headers = self.appointments_sheet.row_values(1)
            if not headers:
                headers = ["id"] + list(appointment_data.keys())
                self.appointments_sheet.append_row(headers)
                print(f"Created headers: {headers}")
            else:
                # Check for and add any missing columns
                for key in appointment_data:
                    if key not in headers:
                        headers.append(key)
                        col_idx = len(headers)
                        self.appointments_sheet.update_cell(1, col_idx, key)
                        print(f"Added missing column: {key}")
            
            # Prepare the row data
            row = [appointment_id]
            for h in headers[1:]:  # Skip the ID column
                row.append(str(appointment_data.get(h, "")))  # Convert all values to string
            
            # Append the row
            self.appointments_sheet.append_row(row)
            print(f"Successfully added appointment row: {row}")
            
            return True
        except Exception as e:
            print(f"ERROR in book_appointment: {str(e)}")
            return False

    def get_appointments(self, patient_id: str = None, date: str = None) -> List[Dict]:
        """Get appointments, filtered by patient ID and/or date"""
        appointments = []
        
        for appt_id, appt_data in self.data["appointments"].items():
            include = True
            
            if patient_id and appt_data.get("patient_id") != patient_id:
                include = False
            
            if date and appt_data.get("date") != date:
                include = False
            
            if include:
                appointments.append({"id": appt_id, **appt_data})
        
        return appointments

    def save_partial_patient_data(self, patient_id: str, data: dict):
        """Save or update partial patient data and persist it to the Google Sheet"""
        # Update in-memory cache
        if patient_id not in self.data["patients"]:
            self.data["patients"][patient_id] = {}
        self.data["patients"][patient_id].update(data)

        # Get existing patient IDs
        patient_ids = self.patients_sheet.col_values(1)
        headers = self.patients_sheet.row_values(1)

        # If no headers, initialize
        if not headers:
            headers = ["id"] + list(data.keys())
            self.patients_sheet.append_row(headers)

        # Add any missing headers
        updated = False
        for key in data:
            if key not in headers:
                headers.append(key)
                col_idx = len(headers)
                self.patients_sheet.update_cell(1, col_idx, key)
                updated = True

        # If patient already exists, update the corresponding row
        if patient_id in patient_ids:
            row_idx = patient_ids.index(patient_id) + 1
            existing_headers = self.patients_sheet.row_values(1)
            for key, value in data.items():
                if key in existing_headers:
                    col_idx = existing_headers.index(key) + 1
                    self.patients_sheet.update_cell(row_idx, col_idx, value)
        else:
            # If not present, create a new row
            row = [patient_id]
            for header in headers[1:]:  # skip 'id'
                row.append(data.get(header, ""))
            self.patients_sheet.append_row(row)

# ---- Memory Component ----
class MedicalChatMemory:
    def __init__(self):
        """Initialize chat memory with conversation history and booking state"""
        # For conversation memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", 
            return_messages=True
        )
        
        # For booking workflow
        self.booking_state = {}
        self.is_booking_active = False  # Flag to indicate booking flow is active
        
        # Current patient tracking
        self.current_patient_id = None
    
    def start_booking_flow(self):
        """Start a new booking flow"""
        self.booking_state = {
            "in_progress": True,
            "step": "select_doctor",  # First step is always doctor selection
            "started_at": datetime.now().isoformat()
        }
        self.is_booking_active = True  # Set flag to true when booking starts
        print("Booking flow started, LLM responses disabled")
    
    def update_booking_state(self, **kwargs):
        """Update the booking state with new information"""
        self.booking_state.update(kwargs)
    
    def clear_booking_state(self):
        """Clear the booking state"""
        self.booking_state = {}
        self.is_booking_active = False  # Reset flag when booking ends
        print("Booking flow ended, LLM responses re-enabled")
    
    def set_current_patient(self, patient_id):
        """Set the current patient ID"""
        self.current_patient_id = patient_id
    
    def add_message(self, user_message, bot_response):
        """Add a message pair to memory"""
        self.memory.chat_memory.add_user_message(user_message)
        self.memory.chat_memory.add_ai_message(bot_response)
    
    def clear_memory(self):
        """Clear conversation memory"""
        self.memory.clear()
        self.booking_state = {}
        self.is_booking_active = False
        self.current_patient_id = None

# ---- Main Medical Chatbot Class ----
class MedicalChatbot:
    def __init__(self):
        # Initialize components
        self.doc_handler = MedicalDocumentHandler()
        self.prompt_manager = MedicalPromptManager()
        self.database = MedicalDatabase()
        self.memory = MedicalChatMemory()
        
        # Initialize language model using Google Gemini
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.2
        )
        
        # Create retrieval chain for medical knowledge
        self.retrieval_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.doc_handler.vector_store.as_retriever(),
            memory=self.memory.memory
        )
        
        # Create tools for the agent
        tools = [
            Tool(
                name="Medical Knowledge Base",
                func=self._query_medical_knowledge,
                description="Useful for answering questions about medical procedures and health information"
            ),
            Tool(
                name="Book Appointment",
                func=self._handle_booking,
                description="Use this to book a medical appointment"
            ),
            Tool(
                name="Store Patient Information",
                func=self._store_patient_info,
                description="Use this to store patient information"
            ),
            Tool(
                name="View Appointments",
                func=self._view_appointments,
                description="Use this to view a patient's upcoming appointments by phone number"
            )
        ]
  
        # Initialize agent
        self.agent = initialize_agent(
            tools=tools,
            llm=self.llm,
            agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
            verbose=True,
            memory=self.memory.memory
        )

    def _query_medical_knowledge(self, query: str) -> str:
        """Query the medical knowledge base for information"""
        relevant_docs = self.doc_handler.search_docs(query)
        context = "\n".join(relevant_docs)

        prompt_template = ChatPromptTemplate.from_template("""
        You are a helpful medical assistant. Use the following context to answer the user's question.

        Context:
        {context}

        Question:
        {query}

        Answer:
        """)

        prompt = prompt_template.format_messages(context=context, query=query)

        # LLM setup using Google Gemini via LangChain
        llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.5,
        google_api_key=os.getenv("google_api_key")  # make sure this is set in your .env
        )

        # Get response from Gemini
        response = llm.invoke(prompt)
        return response.content

    def reset_conversation(self):
        """Reset the chatbot's memory to prevent hallucinations"""
        self.memory.clear_memory()
        # Re-initialize the retrieval chain with fresh memory
        self.retrieval_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.doc_handler.vector_store.as_retriever(),
            memory=self.memory.memory
        )
        return "Memory has been cleared. Starting fresh conversation."
                
    def _handle_booking(self, input_text: str, phone: Optional[str] = None) -> str:
        """Handle appointment booking workflow with strict hardcoded flow"""
        # Check for direct booking start
        if input_text.lower() == "start" or any(keyword in input_text.lower() for keyword in ["book", "appointment", "schedule", "see a doctor"]):
            # Clear any existing booking state to start fresh
            self.memory.clear_booking_state()
            self.memory.start_booking_flow()
            
            # Log the start of a new booking
            print(f"Starting new booking flow at {datetime.now()}")
            
            # STEP 1: Start with specialty selection
            # Get unique specialties from database
            doctors = self.database.data["doctors"]
            specialties = set(doc_info["specialty"] for doc_id, doc_info in doctors.items())
            specialty_options = {chr(65 + i): specialty for i, specialty in enumerate(sorted(specialties))}
            
            self.memory.update_booking_state(specialty_options=specialty_options, step="select_specialty")
            
            # HARDCODED response for specialty selection
            specialty_list = []
            for option, specialty in specialty_options.items():
                specialty_list.append(f"{option}. {specialty}")
            
            formatted_list = "\n".join(specialty_list)
            return f"Let's book your appointment. First, please select a medical specialty by typing the corresponding letter:\n\n{formatted_list}"
        
        # Check if we have an active booking flow
        if not self.memory.is_booking_active:
            # This should not happen with our new flow control
            self.memory.start_booking_flow()
            
            # Log the start of a new booking
            print(f"WARNING: Booking function called without active flow. Starting at {datetime.now()}")
            
            # Start with specialty selection
            doctors = self.database.data["doctors"]
            specialties = set(doc_info["specialty"] for doc_id, doc_info in doctors.items())
            specialty_options = {chr(65 + i): specialty for i, specialty in enumerate(sorted(specialties))}
            
            self.memory.update_booking_state(specialty_options=specialty_options, step="select_specialty")
            
            # HARDCODED response for specialty selection
            specialty_list = []
            for option, specialty in specialty_options.items():
                specialty_list.append(f"{option}. {specialty}")
            
            formatted_list = "\n".join(specialty_list)
            return f"Let's book your appointment. First, please select a medical specialty by typing the corresponding letter:\n\n{formatted_list}"
        
        # Log the current state and input for debugging
        booking_state = self.memory.booking_state
        print(f"Current booking state: {json.dumps(booking_state)}")
        print(f"User input: {input_text}")
        
        # Get current step from state
        step = booking_state.get("step")
        
        # Helper function to check appointment availability
        def get_available_slots(doctor_id, date, time_preference=None):
            """Return available time slots for a doctor on a specific date"""
            all_appointments = self.database.data.get("appointments", {})
            booked_times = []
            
            # Find all booked slots for this doctor on this date
            for _, appt_data in all_appointments.items():
                if (appt_data.get("doctor_id") == doctor_id and 
                    appt_data.get("date") == date and
                    appt_data.get("status") != "cancelled"):
                    booked_times.append(appt_data.get("time"))
            
            # Define time slots based on preference
            morning_slots = ["10:45-11:00 AM", "11:00-11:15 AM", "11:15-11:30 AM"]
            evening_slots = ["1:45-2:00 PM", "2:00-2:15 PM", "2:15-2:30 PM"]
            
            if time_preference == "morning":
                all_slots = morning_slots
            elif time_preference == "evening":
                all_slots = evening_slots
            else:
                all_slots = morning_slots + evening_slots
            
            # Filter out booked slots
            available_slots = [slot for slot in all_slots if slot not in booked_times]
            return available_slots
        
        # Helper function to get available dates
        def get_available_dates(doctor_id, days_to_check=7):
            """Return up to 3 dates with available slots within the next specified days"""
            available_dates = []
            current_date = datetime.now()
            
            for i in range(1, days_to_check+1):
                date_to_check = (current_date + timedelta(days=i)).strftime("%Y-%m-%d")
                if get_available_slots(doctor_id, date_to_check):
                    available_dates.append(date_to_check)
                    if len(available_dates) >= 3:  # Get at most 3 dates
                        break
            
            return available_dates
        
        # STRICTLY SEQUENTIAL FLOW with hardcoded responses for each step
        # NEW STEP: Select specialty
        if step == "select_specialty":
            # Check if user entered an option letter
            input_letter = input_text.strip().upper()
            specialty_options = booking_state.get("specialty_options", {})
            
            selected_specialty = None
            
            # Try to match by letter
            if input_letter in specialty_options:
                selected_specialty = specialty_options[input_letter]
            
            # Try to match by name
            if not selected_specialty:
                for letter, specialty in specialty_options.items():
                    if specialty.lower() in input_text.lower():
                        selected_specialty = specialty
                        break

            if selected_specialty:
                # Filter doctors by selected specialty
                doctors = self.database.data["doctors"]
                filtered_doctors = {doc_id: doc_info for doc_id, doc_info in doctors.items()
                                  if doc_info["specialty"] == selected_specialty}
                
                if not filtered_doctors:
                    # Fallback in case of error
                    return f"Sorry, we currently don't have any doctors available in {selected_specialty}. Please select another specialty."
                
                # Create options for filtered doctors
                options = {chr(65 + i): doc_id for i, (doc_id, _) in enumerate(filtered_doctors.items())}
                
                # Update booking state
                self.memory.update_booking_state(
                    selected_specialty=selected_specialty,
                    doctor_options=options,
                    step="select_doctor"
                )
                
                # HARDCODED response for doctor selection
                doctor_list = []
                for option, doc_id in options.items():
                    doc_info = doctors[doc_id]
                    doctor_list.append(f"{option}. {doc_info['name']} ({doc_info['specialty']})")
                
                formatted_list = "\n".join(doctor_list)
                return f"Great! You've selected {selected_specialty}. Please select a doctor by typing the corresponding letter:\n\n{formatted_list}"
            
            # Neither option letter nor specialty matched
            # HARDCODED specialty selection retry prompt
            specialty_list = []
            for option, specialty in specialty_options.items():
                specialty_list.append(f"{option}. {specialty}")
            
            formatted_list = "\n".join(specialty_list)
            return f"I couldn't identify which specialty you'd like. Please select from the options below by entering the letter:\n\n{formatted_list}"
        
        elif step == "select_doctor":
            # Check if user entered an option letter
            input_letter = input_text.strip().upper()
            doctor_options = booking_state.get("doctor_options", {})
            
            selected_doctor_id = None
            
            # Try to match by letter
            if input_letter in doctor_options:
                selected_doctor_id = doctor_options[input_letter]
            
            # Try to match by doctor name
            if not selected_doctor_id:
                for doc_id, doc_info in self.database.data["doctors"].items():
                    if doc_info["name"].lower() in input_text.lower():
                        selected_doctor_id = doc_id
                        break
            
            if selected_doctor_id:
                doc_info = self.database.data["doctors"][selected_doctor_id]
                
                # Get available dates
                available_dates = get_available_dates(selected_doctor_id)
                
                if not available_dates:
                    # No dates available for this doctor
                    return f"I'm sorry, Dr. {doc_info['name']} doesn't have any available appointments in the next week. Would you like to select another doctor?"
                
                self.memory.update_booking_state(
                    doctor_id=selected_doctor_id, 
                    available_dates=available_dates,
                    step="select_date"
                )
                
                # Format date options
                date_options = "\n- " + "\n- ".join(available_dates)
                
                return f"When would you like to book your appointment with {doc_info['name']}?\n\nAvailable dates are:{date_options}\n\nPlease provide a date in Y-M-D format."
            
            # Neither option letter nor doctor name matched
            # HARDCODED doctor selection retry prompt
            doctors = self.database.data["doctors"]
            options = booking_state.get("doctor_options", {})
            doctor_list = []
            for option, doc_id in options.items():
                doc_info = doctors[doc_id]
                doctor_list.append(f"{option}. {doc_info['name']} ({doc_info['specialty']})")
            
            formatted_list = "\n".join(doctor_list)
            return f"I couldn't identify which doctor you'd like to see. Please select from the options below by entering the letter:\n\n{formatted_list}"

        elif step == "select_date":
            # Simple date extraction
            if '-' in input_text and len(input_text.split('-')) == 3:
                selected_date = input_text.strip()
                doctor_id = booking_state.get("doctor_id")
                available_dates = booking_state.get("available_dates", [])
                
                # Check if the selected date is in the available dates
                if selected_date not in available_dates:
                    date_options = "\n- " + "\n- ".join(available_dates)
                    return f"I'm sorry, that date isn't available. Please select from these dates:{date_options}"
                
                doctor_name = self.database.data["doctors"][doctor_id]["name"]
                
                # Check morning and evening availability
                morning_slots = get_available_slots(doctor_id, selected_date, "morning")
                evening_slots = get_available_slots(doctor_id, selected_date, "evening")
                
                # Add time preference options based on availability
                time_preference_options = []
                if morning_slots:
                    time_preference_options.append("morning")
                if evening_slots:
                    time_preference_options.append("evening")
                
                if not time_preference_options:
                    # This shouldn't happen if we properly filtered dates, but just in case
                    return f"I'm sorry, there are no available slots on {selected_date} with {doctor_name}. Please select another date."
                
                self.memory.update_booking_state(
                    date=selected_date, 
                    time_preference_options=time_preference_options,
                    step="select_time_preference"
                )
                
                # Format the prompt based on available options
                if len(time_preference_options) == 1:
                    preference = time_preference_options[0]
                    return f"For your appointment with {doctor_name} on {selected_date}, only {preference} slots are available. Is that okay? Please type 'yes' or select another date."
                else:
                    return f"For your appointment with {doctor_name} on {selected_date}, do you prefer a morning or evening slot? Please type 'morning' or 'evening'."
            
            # HARDCODED date format error prompt
            available_dates = booking_state.get("available_dates", [])
            date_options = "\n- " + "\n- ".join(available_dates)
            return f"Please provide a date in the format Y-M-D (for example, {available_dates[0]}) from these available dates:{date_options}"
        
        # Time preference step
        elif step == "select_time_preference":
            preference = input_text.strip().lower()
            doctor_id = booking_state.get("doctor_id")
            selected_date = booking_state.get("date")
            time_preference_options = booking_state.get("time_preference_options", [])
            
            # If only one option was available and user says yes
            if len(time_preference_options) == 1 and "yes" in preference:
                preference = time_preference_options[0]
            
            if "morning" in preference and "morning" in time_preference_options:
                # Get available morning slots
                available_slots = get_available_slots(doctor_id, selected_date, "morning")
                self.memory.update_booking_state(
                    time_preference="morning", 
                    available_slots=available_slots,
                    step="select_time"
                )
            elif "evening" in preference and "evening" in time_preference_options:
                # Get available evening slots
                available_slots = get_available_slots(doctor_id, selected_date, "evening")
                self.memory.update_booking_state(
                    time_preference="evening", 
                    available_slots=available_slots,
                    step="select_time"
                )
            else:
                # If preference not clear or not available, ask again
                if len(time_preference_options) == 1:
                    only_option = time_preference_options[0]
                    return f"Only {only_option} slots are available. Please type 'yes' to confirm or select another date."
                
                options_text = " or ".join(time_preference_options)
                return f"Please specify if you prefer a {options_text} appointment."
            
            # Get the doctor and date from booking state
            doctor_name = self.database.data["doctors"][doctor_id]["name"]
            
            # Format time slots
            available_slots = self.memory.booking_state.get("available_slots", [])
            slots_text = "\n- " + "\n- ".join(available_slots)
            
            # HARDCODED time selection prompt with filtered slots
            return f"🌞For {selected_date} with {doctor_name}, we have the following {preference} slots available:{slots_text}\n\nWhat time works for you?"
        
        elif step == "select_time":
            # Available slots from booking state
            available_slots = booking_state.get("available_slots", [])
            selected_time = None
            
            # Try to find the time in user input
            for time in available_slots:
                if time.lower() in input_text.lower():
                    selected_time = time
                    break
            
            if selected_time:
                self.memory.update_booking_state(time=selected_time, step="collect_name")
                
                # HARDCODED name collection prompt
                return "Please enter your full name for booking:📄 "
            
            # HARDCODED time selection retry prompt with only relevant slots
            slots_text = "\n- " + "\n- ".join(available_slots)
            return f"🌞Please select one of the following available time slots:{slots_text}"
        
        elif step == "collect_name":
            name = input_text.strip()
            if not name:
                return "Your name is required. Please enter your full name:"

            self.memory.update_booking_state(name=name)

            patient_id = self.memory.current_patient_id or f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self.memory.set_current_patient(patient_id)
            self.database.save_partial_patient_data(patient_id, {"name": name})

            if phone:
                self.memory.update_booking_state(phone=phone, step="collect_age")
                self.database.save_partial_patient_data(patient_id, {"phone": phone})
                return "Great! Now, please enter your age 🧓:"
            else:
                self.memory.update_booking_state(step="collect_phone")
                return "Okay, please enter your phone number 📝:"

        elif step == "collect_phone":
            phone = input_text.strip()
            if not phone:
                return "Your phone number is required. Please enter your phone number 📝:"
            
            self.memory.update_booking_state(phone=phone, step="collect_age")
            
            # Update patient record
            patient_id = self.memory.current_patient_id
            self.database.save_partial_patient_data(patient_id, {"phone": phone})
            
            return "Thanks! Please enter your age 🧓:"

        elif step == "collect_age":
            age = input_text.strip()
            if not age.isdigit() or not (0 < int(age) < 120):
                return "Please enter a valid age (e.g., 25):"
            
            self.memory.update_booking_state(age=age, step="collect_gender")
            
            # Save to patient record
            patient_id = self.memory.current_patient_id
            self.database.save_partial_patient_data(patient_id, {"age": age})
            
            return "Got it! Now, please specify your gender (Male/Female/Other):"
        
        elif step == "collect_gender":
            gender = input_text.strip().lower()
            if gender not in ["male", "female", "other"]:
                return "Please enter a valid gender: Male, Female, or Other:"
            
            self.memory.update_booking_state(gender=gender, step="confirm")
            
            # Save to patient record
            patient_id = self.memory.current_patient_id
            self.database.save_partial_patient_data(patient_id, {"gender": gender})
            
            return "Lastly, please provide the reason for your visit to confirm your appointment:"

        elif step == "confirm":
            # Store the reason for visit
            reason = input_text.strip()
            self.memory.update_booking_state(reason=reason, step="complete")
            
            # Debug log
            print('=== CONFIRMING APPOINTMENT ===')
            print(f"Current booking state: {json.dumps(booking_state)}")
            
            # Generate appointment ID
            appointment_id = f"APPT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Get patient information
            name = booking_state.get("name")
            phone = booking_state.get("phone")
            
            if not name or not phone:
                self.memory.clear_booking_state()
                # HARDCODED error prompt
                return "Missing patient information. Booking process has been reset. Please try again by asking to book an appointment."
            
            # Get or create patient ID
            patient_id = self.memory.current_patient_id
            if not patient_id:
                patient_id = self.database.find_patient_id(name, phone)
                
                if not patient_id:
                    patient_id = f"patient_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    patient_data = {
                        "name": name,
                        "phone": phone
                    }
                    self.database.add_patient(patient_id, patient_data)
                    self.memory.set_current_patient(patient_id)
            
            # Create appointment data
            appointment_data = {
                "doctor_id": booking_state.get("doctor_id"),
                "patient_id": patient_id,
                "date": booking_state.get("date"),
                "time": booking_state.get("time"),
                "reason": reason,
                "name": name,
                "phone": phone,
                "status": "confirmed",
                "specialty": booking_state.get("selected_specialty")  # Store the specialty
            }
            
            # Validate required fields
            missing_fields = [f for f in ["doctor_id", "date", "time"] if not appointment_data.get(f)]
            if missing_fields:
                self.memory.clear_booking_state()
                # HARDCODED missing fields prompt
                return "Missing appointment details. Booking process has been reset. Please try again by asking to book an appointment."
            
            # Store in database
            success = self.database.book_appointment(appointment_id, appointment_data)
            if not success:
                self.memory.clear_booking_state()
                # HARDCODED db error prompt
                return "System error: Unable to save appointment. Please try again later or contact our office directly."
            
            doctor_name = self.database.data["doctors"][booking_state.get("doctor_id")]["name"]
            specialty = booking_state.get("selected_specialty")
            
            # Clear booking state after successful save
            self.memory.clear_booking_state()
            
            # HARDCODED confirmation message with all details in a standardized format
            return f"""Appointment Successfully Booked!🎉 

        Appointment ID: {appointment_id}
        Patient: {name}
        Doctor: {doctor_name} 
        Specialty: {specialty}
        Date: {booking_state.get("date")}
        Time: {booking_state.get("time")}
        Phone: {phone}
        Reason: {reason}

        Thank you for booking with us. You will receive a confirmation text message shortly. If you need to reschedule or cancel, please contact us and reference your Appointment ID."""
 
    def _view_appointments(self, phone: str) -> str:
        """Handler to view appointments by phone number (directly from appointments data)"""
        if not phone:
            return "To view your appointments, please provide your phone number."        
        now = datetime.now()
        future_appointments = []
        # Debug line to check what's in the database
        print(f"Searching for appointments with phone: {phone}")
        print(f"All appointments: {self.database.data['appointments']}")

        for appt_id, appt in self.database.data["appointments"].items():
            # Skip cancelled appointments
            if appt.get("status", "").lower() == "cancelled":
                continue
            # Normalize stored phone number to ensure consistent comparison
            stored_phone = str(appt.get("phone", "")).strip()
            stored_phone = re.sub(r'[^0-9]', '', stored_phone)
            
            print(f"Comparing: stored phone '{stored_phone}' with input '{phone}'")
            
            if stored_phone == phone:
                try:
                    # Handle different time formats (12-hour vs 24-hour)
                    date_str = appt.get('date', '')
                    # Extract only the starting time from a range like '10:00 to 10:15 AM' or '10:00-10:15 AM'
                    time_str_raw = appt.get('time', '').strip()
                    match = re.match(r'(\d{1,2}:\d{2})\s*(?:to|-|–)\s*\d{1,2}:\d{2}\s*([APap][Mm])', time_str_raw)
                    if match:
                        time_str = f"{match.group(1)} {match.group(2).upper()}"  # Normalize like '10:00 AM'
                    else:
                        time_str = time_str_raw  # fallback to the original (in case it's a single time)

                    
                    # Try different time formats
                    time_formats = [
                        "%Y-%m-%d %H:%M:%S",  # 2025-05-03 14:00:00
                        "%Y-%m-%d %I:%M %p",  # 2025-05-03 10:00 AM
                        "%Y-%m-%d %I:%M%p",   # 2025-05-03 10:00AM
                        "%Y-%m-%d %H:%M"      # 2025-05-03 14:00
                    ]
                    
                    appt_datetime = None
                    for fmt in time_formats:
                        try:
                            appt_datetime = datetime.strptime(f"{date_str} {time_str}", fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not appt_datetime:
                        print(f"Could not parse datetime: {date_str} {time_str}")
                        continue
                        
                    print(f"Appointment datetime: {appt_datetime}, Now: {now}")
                    
                    if appt_datetime >= now:
                        doctor_name = "Unknown"
                        doctor_id = appt.get("doctor_id")
                        if doctor_id and doctor_id in self.database.data["doctors"]:
                            doctor_name = self.database.data["doctors"][doctor_id].get("name", "Unknown")
                        else:
                            # If doctor_id is not present or invalid, use doctor name directly if available
                            doctor_name = appt.get("doctor", doctor_name)

                        future_appointments.append({
                            "id": appt_id,
                            "doctor": doctor_name,
                            "specialty": appt.get("specialty", "General"),
                            "date": appt.get("date", "Unknown"),
                            "time": appt.get("time", "Unknown"),
                            "reason": appt.get("reason", "Not specified")
                        })
                except Exception as e:
                    print(f"Error processing appointment {appt_id}: {str(e)}")
                    continue

        # Sort appointments by date and time
        future_appointments.sort(key=lambda x: (x["date"], x["time"]))

        if not future_appointments:
            return f"No upcoming appointments found for phone number {phone}. Would you like to book a new one?"

        # Format output
        formatted = []
        for i, appt in enumerate(future_appointments, 1):
            formatted.append(f"""Appointment #{i}:
                Doctor: {appt['doctor']} ({appt['specialty']})
                Date: {appt['date']}
                Time: {appt['time']}
                Reason: {appt['reason']}
                Appointment ID: {appt['id']}""")

        # Join outside the f-string to avoid backslash in {}
        appointments_text = "\n\n".join(formatted)

        return f"""Here are your upcoming appointments:\n\n{appointments_text}\n\nIf you need to reschedule or cancel, please provide your Appointment ID."""

    def _cancel_appointment(self, appointment_id: str) -> str:
        """Cancel an appointment by ID"""
        try:
            print("Cancel appointment---->",appointment_id)
            # Validate appointment ID
            if not appointment_id or not isinstance(appointment_id, str):
                return "Invalid appointment ID. Please provide the appointment ID in the format APPT-YYYYMMDDHHMMSS."
            
            # Make sure appointment exists
            if appointment_id not in self.database.data["appointments"]:
                return f"No appointment found with ID {appointment_id}. Please check the ID and try again."
            
            # Get appointment details
            appointment = self.database.data["appointments"][appointment_id]
            
            # Check if appointment is already cancelled
            if appointment.get("status") == "cancelled":
                return f"Appointment {appointment_id} has already been cancelled."
            # Check if appointment is in the past
            try:
                appointment_date = appointment.get("date")
                appointment_time = appointment.get("time")
                
                if appointment_date:
                    # Try different time formats
                    time_formats = [
                        "%Y-%m-%d %H:%M:%S",  # 2025-05-03 14:00:00
                        "%Y-%m-%d %I:%M %p",  # 2025-05-03 10:00 AM
                        "%Y-%m-%d %I:%M%p",   # 2025-05-03 10:00AM
                        "%Y-%m-%d %H:%M"      # 2025-05-03 14:00
                    ]
                    
                    appt_datetime = None
                    for fmt in time_formats:
                        try:
                            appt_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", fmt)
                            break
                        except ValueError:
                            continue
                    
                    if appt_datetime and appt_datetime < datetime.now():
                        return f"Cannot cancel appointment {appointment_id} as it has already passed."
            except Exception as e:
                print(f"Error parsing appointment date: {str(e)}")
                # Continue with cancellation even if date parsing fails
            
            # Get doctor and patient info for the response
            doctor_name = "Unknown"
            doctor_id = appointment.get("doctor_id")
            if doctor_id and doctor_id in self.database.data["doctors"]:
                doctor_name = self.database.data["doctors"][doctor_id].get("name", "Unknown")
            
            patient_name = appointment.get("name", "Unknown")
            
            # Update appointment status in database
            appointment["status"] = "cancelled"
            appointment["cancelled_at"] = datetime.now().isoformat()
            
            # Update the worksheet with the cancelled status
            try:
                # Get the row index for this appointment
                appointment_ids = self.database.appointments_sheet.col_values(1)
                if appointment_id in appointment_ids:
                    row_idx = appointment_ids.index(appointment_id) + 1
                    
                    # Get the status column index
                    headers = self.database.appointments_sheet.row_values(1)
                    status_col = headers.index("status") + 1 if "status" in headers else None
                    
                    if status_col:
                        self.database.appointments_sheet.update_cell(row_idx, status_col, "cancelled")
                        
                        # Add cancelled_at column if it doesn't exist
                        if "cancelled_at" not in headers:
                            cancelled_at_col = len(headers) + 1
                            self.database.appointments_sheet.update_cell(1, cancelled_at_col, "cancelled_at")
                            self.database.appointments_sheet.update_cell(row_idx, cancelled_at_col, datetime.now().isoformat())
                        else:
                            cancelled_at_col = headers.index("cancelled_at") + 1
                            self.database.appointments_sheet.update_cell(row_idx, cancelled_at_col, datetime.now().isoformat())
            except Exception as e:
                print(f"Error updating spreadsheet: {str(e)}")
                # Continue despite spreadsheet update errors
            
            return f"""Appointment Cancelled Successfully! ✅

    Appointment ID: {appointment_id}
    Patient: {patient_name}
    Doctor: {doctor_name}
    Date: {appointment.get("date", "Unknown")}
    Time: {appointment.get("time", "Unknown")}

    Your appointment has been cancelled. If you wish to book a new appointment, please say "book appointment".
    """
        except Exception as e:
            print(f"ERROR in cancel_appointment: {str(e)}")
            return f"There was an error cancelling your appointment: {str(e)}. Please try again or contact our office directly."

    def _reschedule_appointment(self, appointment_id: str, new_date: str = None, new_time: str = None) -> str:
        """Reschedule an appointment by ID, optionally with new date/time"""
        try:
            # Validate appointment ID
            if not appointment_id or not isinstance(appointment_id, str):
                return "Invalid appointment ID. Please provide the appointment ID in the format APPT-YYYYMMDDHHMMSS."
            
            # Make sure appointment exists
            if appointment_id not in self.database.data["appointments"]:
                return f"No appointment found with ID {appointment_id}. Please check the ID and try again."
            
            # Get appointment details
            appointment = self.database.data["appointments"][appointment_id]
            
            # Check if appointment is already cancelled
            if appointment.get("status") == "cancelled":
                return f"Appointment {appointment_id} has been cancelled and cannot be rescheduled. Please book a new appointment."
            print("Reschedule appointment---->",appointment)
            # Check if appointment is in the past
            try:
                appointment_date = appointment.get("date")
                appointment_time = appointment.get("time")
                
                if appointment_date:
                    # Try different time formats including time range format
                    time_formats = [
                        "%Y-%m-%d %H:%M:%S",      # 2025-05-03 14:00:00
                        "%Y-%m-%d %I:%M %p",      # 2025-05-03 10:00 AM
                        "%Y-%m-%d %I:%M%p",       # 2025-05-03 10:00AM
                        "%Y-%m-%d %H:%M"          # 2025-05-03 14:00
                    ]
                    
                    appt_datetime = None
                    
                    # Handle time range format (e.g., "11:00-11:15 AM")
                    time_range_match = re.match(r'(\d{1,2}:\d{2})-\d{1,2}:\d{2}\s*(AM|PM|am|pm)?', appointment_time)
                    if time_range_match:
                        # Extract just the start time for comparison
                        start_time = time_range_match.group(1)
                        am_pm = time_range_match.group(2) or ""
                        parsed_time = f"{start_time} {am_pm}".strip()
                        
                        # Try parsing with the extracted start time
                        for fmt in ["%Y-%m-%d %I:%M %p", "%Y-%m-%d %I:%M"]:
                            try:
                                appt_datetime = datetime.strptime(f"{appointment_date} {parsed_time}", fmt)
                                break
                            except ValueError:
                                continue
                    else:
                        # Try standard formats
                        for fmt in time_formats:
                            try:
                                appt_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", fmt)
                                break
                            except ValueError:
                                continue
                    
                    if appt_datetime and appt_datetime < datetime.now():
                        return f"Cannot reschedule appointment {appointment_id} as it has already passed."
            except Exception as e:
                print(f"Error parsing appointment date: {str(e)}")
                # Continue with rescheduling even if date parsing fails
            
            # Get doctor and patient info for the response
            doctor_id = appointment.get("doctor_id")
            if not doctor_id or doctor_id not in self.database.data["doctors"]:
                return f"Error finding doctor information for appointment {appointment_id}. Please contact our office directly."
            
            doctor_name = self.database.data["doctors"][doctor_id].get("name", "Unknown")
            patient_name = appointment.get("name", "Unknown")
            
            # If no new date/time provided, start the rescheduling flow
            if not new_date and not new_time:
                # Get available dates for the doctor
                available_dates = self._get_available_dates(doctor_id)
                
                if not available_dates:
                    return f"No available dates found for {doctor_name} in the next week. Please contact our office directly to reschedule."
                
                # Start the rescheduling workflow
                self.memory.start_booking_flow()
                self.memory.update_booking_state(
                    step="reschedule_date",
                    doctor_id=doctor_id,
                    original_appointment_id=appointment_id,
                    available_dates=available_dates
                )
                
                # Format date options
                date_options = "\n- " + "\n- ".join(available_dates)
                
                return f"Let's reschedule your appointment with {doctor_name}.\n\nAvailable dates are:{date_options}\n\nPlease provide a date in Y-M-D format."
            
            # If we have a new date but no time, get available times
            if new_date and not new_time:
                # Validate date format (YYYY-MM-DD)
                if not re.match(r'\d{4}-\d{2}-\d{2}', new_date):
                    return "Please provide the date in Y-M-D format (e.g., 2025-05-10)."
                
                # Get available time slots for this date
                morning_slots = self._get_available_slots(doctor_id, new_date, "morning")
                evening_slots = self._get_available_slots(doctor_id, new_date, "evening")
                
                if not morning_slots and not evening_slots:
                    return f"No available time slots found for {doctor_name} on {new_date}. Please select another date."
                
                # Add time preference options based on availability
                time_preference_options = []
                if morning_slots:
                    time_preference_options.append("morning")
                if evening_slots:
                    time_preference_options.append("evening")
                
                # Start the time selection workflow
                self.memory.update_booking_state(
                    step="reschedule_time_preference",
                    doctor_id=doctor_id,
                    original_appointment_id=appointment_id,
                    date=new_date,
                    time_preference_options=time_preference_options
                )
                
                # Format the prompt based on available options
                if len(time_preference_options) == 1:
                    preference = time_preference_options[0]
                    return f"🌞For your rescheduled appointment with {doctor_name} on {new_date}, only {preference} slots are available. Is that okay? Please type 'yes' or select another date."
                else:
                    return f"For your rescheduled appointment with {doctor_name} on {new_date}, do you prefer a morning or evening slot? Please type 'morning' or 'evening'."
            
            # If we have both date and time, update the appointment
            if new_date and new_time:
                # Validate date format (YYYY-MM-DD)
                if not re.match(r'\d{4}-\d{2}-\d{2}', new_date):
                    return "Please provide the date in YYYY-MM-DD format (e.g., 2025-05-10)."
                
                # Handle time range format in new_time
                time_to_check = new_time
                time_range_match = re.match(r'(\d{1,2}:\d{2})-\d{1,2}:\d{2}\s*(AM|PM|am|pm)?', new_time)
                if time_range_match:
                    # Extract the start time for slot checking
                    start_time = time_range_match.group(1)
                    am_pm = time_range_match.group(2) or ""
                    time_to_check = f"{start_time} {am_pm}".strip()
                
                # Check if the slot is available
                available_slots = self._get_available_slots(doctor_id, new_date)
                
                # Normalize available slots for comparison
                normalized_available_slots = []
                for slot in available_slots:
                    slot_match = re.match(r'(\d{1,2}:\d{2})-\d{1,2}:\d{2}\s*(AM|PM|am|pm)?', slot)
                    if slot_match:
                        # Extract start time for comparison
                        start = slot_match.group(1)
                        modifier = slot_match.group(2) or ""
                        normalized_available_slots.append(f"{start} {modifier}".strip())
                    else:
                        normalized_available_slots.append(slot)
                
                if time_to_check not in available_slots and time_to_check not in normalized_available_slots:
                    return f"The slot at {new_time} on {new_date} is not available. Please select from: {', '.join(available_slots)}"
                
                # Update appointment in database
                appointment["date"] = new_date
                appointment["time"] = new_time
                appointment["rescheduled"] = True
                appointment["rescheduled_at"] = datetime.now().isoformat()
                
                # Update the worksheet with the new date and time
                try:
                    # Get the row index for this appointment
                    appointment_ids = self.database.appointments_sheet.col_values(1)
                    if appointment_id in appointment_ids:
                        row_idx = appointment_ids.index(appointment_id) + 1
                        
                        # Get the column indices
                        headers = self.database.appointments_sheet.row_values(1)
                        date_col = headers.index("date") + 1 if "date" in headers else None
                        time_col = headers.index("time") + 1 if "time" in headers else None
                        
                        if date_col:
                            self.database.appointments_sheet.update_cell(row_idx, date_col, new_date)
                        if time_col:
                            self.database.appointments_sheet.update_cell(row_idx, time_col, new_time)
                        
                        # Add rescheduled flag if it doesn't exist
                        if "rescheduled" not in headers:
                            rescheduled_col = len(headers) + 1
                            self.database.appointments_sheet.update_cell(1, rescheduled_col, "rescheduled")
                            self.database.appointments_sheet.update_cell(row_idx, rescheduled_col, "True")
                            
                            # Add rescheduled_at column
                            rescheduled_at_col = len(headers) + 2
                            self.database.appointments_sheet.update_cell(1, rescheduled_at_col, "rescheduled_at")
                            self.database.appointments_sheet.update_cell(row_idx, rescheduled_at_col, datetime.now().isoformat())
                        else:
                            rescheduled_col = headers.index("rescheduled") + 1
                            self.database.appointments_sheet.update_cell(row_idx, rescheduled_col, "True")
                            
                            if "rescheduled_at" in headers:
                                rescheduled_at_col = headers.index("rescheduled_at") + 1
                                self.database.appointments_sheet.update_cell(row_idx, rescheduled_at_col, datetime.now().isoformat())
                except Exception as e:
                    print(f"Error updating spreadsheet: {str(e)}")
                    # Continue despite spreadsheet update errors
                
                # Clear the booking state
                self.memory.clear_booking_state()
                
                return f"""Appointment Rescheduled Successfully! ✅

    Appointment ID: {appointment_id}
    Patient: {patient_name}
    Doctor: {doctor_name}
    NEW Date: {new_date}
    NEW Time: {new_time}

    Your appointment has been rescheduled. We'll see you then!
    """
            
            # If we reach here, something went wrong
            return "There was an error processing your rescheduling request. Please provide both a date (YYYY-MM-DD) and time, or contact our office directly."
        except Exception as e:
            print(f"ERROR in reschedule_appointment: {str(e)}")
            return f"There was an error rescheduling your appointment: {str(e)}. Please try again or contact our office directly."

    # Helper method to get available dates (extracted from _handle_booking)
    def _get_available_dates(self, doctor_id, days_to_check=7):
        """Return up to 3 dates with available slots within the next specified days"""
        available_dates = []
        current_date = datetime.now()
        
        for i in range(1, days_to_check+1):
            date_to_check = (current_date + timedelta(days=i)).strftime("%Y-%m-%d")
            if self._get_available_slots(doctor_id, date_to_check):
                available_dates.append(date_to_check)
                if len(available_dates) >= 3:  # Get at most 3 dates
                    break
        
        return available_dates

    # Helper method to get available slots (extracted from _handle_booking)
    def _get_available_slots(self, doctor_id, date, time_preference=None):
        """Return available time slots for a doctor on a specific date"""
        all_appointments = self.database.data.get("appointments", {})
        booked_times = []
        
        # Find all booked slots for this doctor on this date
        for _, appt_data in all_appointments.items():
            if (appt_data.get("doctor_id") == doctor_id and 
                appt_data.get("date") == date and
                appt_data.get("status") != "cancelled"):
                booked_times.append(appt_data.get("time"))
        
        # Define time slots based on preference
        morning_slots = ["10:45-11:00 AM", "11:00-11:15 AM", "11:15-11:30 AM"]
        evening_slots = ["1:45-2:00 PM", "2:00-2:15 PM", "2:15-2:30 PM"]
        
        if time_preference == "morning":
            all_slots = morning_slots
        elif time_preference == "evening":
            all_slots = evening_slots
        else:
            all_slots = morning_slots + evening_slots
        
        # Filter out booked slots
        available_slots = [slot for slot in all_slots if slot not in booked_times]
        return available_slots

    # Add these functions to the process_message method
    def process_message(self, message: str, phone: Optional[str] = None) -> str:
        """Process an incoming message with enhanced appointment management"""
        try:
            # Check for reset command
            if message.lower().strip() in ["reset", "clear memory", "restart", "clear cache"]:
                return self.reset_conversation()
            # Check for booking-specific reset
            if message.lower().strip() in ["cancel booking", "stop booking"]:
                self.memory.clear_booking_state()
                return "Booking process canceled. How else can I help you today?"
            
            if self.is_greeting(message):
                return self.prompt_manager.get_prompt("greeting")

            # Debugging: Print incoming message details
            print(f"Processing message: '{message}', phone: {phone}")

            # Extract appointment ID for cancel/reschedule - Do this first
            message_lower = message.lower()
            appointment_id = None
            appt_id_match = re.search(r'APPT-\d{14}', message, re.IGNORECASE)
            if appt_id_match:
                appointment_id = appt_id_match.group(0).upper()
                print(f"Found appointment ID: {appointment_id}")

            # Check for specific request types - more specific patterns first
            is_cancel_request = "cancel" in message_lower and "appointment" in message_lower
            is_reschedule_request = any(phrase in message_lower for phrase in [
                "reschedule appointment", "change appointment", "move appointment",
                "reschedule my appointment", "change my appointment"
            ])
            is_booking_request = "book" in message_lower and "appointment" in message_lower
            is_view_request = any(phrase in message_lower for phrase in [
                "view my appointment", "my appointment", "check appointment", 
                "see my appointment", "do i have appointment"
            ]) and not is_cancel_request and not is_reschedule_request  # Ensure view doesn't override others
            
            # Debug prints
            print(f"Is cancel request: {is_cancel_request}")
            print(f"Is reschedule request: {is_reschedule_request}")
            print(f"Is booking request: {is_booking_request}")
            print(f"Is view request: {is_view_request}")
            
            # Format phone if provided
            if phone and phone.startswith("+"):
                phone = phone[1:]  # Remove + prefix - it was removing +1 but should remove just +
            phone = phone[2:]
            # PRIORITY HANDLING ORDER:
            # 1. First check for cancel and reschedule requests with IDs
            if is_cancel_request and appointment_id:
                print(f"Executing cancel appointment with ID: {appointment_id}")
                return self._cancel_appointment(appointment_id)
            
            if is_reschedule_request and appointment_id:
                print("Executing reschedule appointment")
                # Extract date and time if provided
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
                new_date = date_match.group(0) if date_match else None
                
                # Look for time pattern (e.g., 10:00 AM, 2:00 PM)
                time_match = re.search(r'\d{1,2}:\d{2}\s*(AM|PM)', message, re.IGNORECASE)
                new_time = time_match.group(0) if time_match else None
                
                return self._reschedule_appointment(appointment_id, new_date, new_time)
            
            # 2. Handle booking flow continuations
            if self.memory.is_booking_active:
                print("Continuing active booking flow")
                # Check for rescheduling flow
                if self.memory.booking_state.get("step") == "reschedule_date":
                    # Handle date selection for rescheduling
                    selected_date = message.strip()
                    doctor_id = self.memory.booking_state.get("doctor_id")
                    available_dates = self.memory.booking_state.get("available_dates", [])
                    original_appointment_id = self.memory.booking_state.get("original_appointment_id")
                    
                    if selected_date in available_dates:
                        return self._reschedule_appointment(original_appointment_id, selected_date)
                    else:
                        date_options = "\n- " + "\n- ".join(available_dates)
                        return f"I'm sorry, that date isn't available. Please select from these dates:{date_options}"
                
                elif self.memory.booking_state.get("step") == "reschedule_time_preference":
                    # Handle time preference selection for rescheduling
                    preference = message.strip().lower()
                    doctor_id = self.memory.booking_state.get("doctor_id")
                    selected_date = self.memory.booking_state.get("date")
                    original_appointment_id = self.memory.booking_state.get("original_appointment_id")
                    time_preference_options = self.memory.booking_state.get("time_preference_options", [])
                    
                    # Process time preference
                    if "morning" in preference and "morning" in time_preference_options:
                        available_slots = self._get_available_slots(doctor_id, selected_date, "morning")
                        slots_text = "\n- " + "\n- ".join(available_slots)
                        
                        self.memory.update_booking_state(
                            step="reschedule_time",
                            time_preference="morning",
                            available_slots=available_slots
                        )
                        
                        doctor_name = self.database.data["doctors"][doctor_id]["name"]
                        return f"For {selected_date} with {doctor_name}, we have the following morning slots available:{slots_text}\n\nWhat time works for you?"
                    
                    elif "evening" in preference and "evening" in time_preference_options:
                        available_slots = self._get_available_slots(doctor_id, selected_date, "evening")
                        slots_text = "\n- " + "\n- ".join(available_slots)
                        
                        self.memory.update_booking_state(
                            step="reschedule_time",
                            time_preference="evening",
                            available_slots=available_slots
                        )
                        
                        doctor_name = self.database.data["doctors"][doctor_id]["name"]
                        return f"For {selected_date} with {doctor_name}, we have the following evening slots available:{slots_text}\n\nWhat time works for you?"
                    
                    else:
                        # If preference not clear or not available, ask again
                        if len(time_preference_options) == 1:
                            only_option = time_preference_options[0]
                            return f"Only {only_option} slots are available. Please type 'yes' to confirm or select another date."
                        
                        options_text = " or ".join(time_preference_options)
                        return f"Please specify if you prefer a {options_text} appointment."
                
                elif self.memory.booking_state.get("step") == "reschedule_time":
                    # Handle time selection for rescheduling
                    available_slots = self.memory.booking_state.get("available_slots", [])
                    selected_time = None
                    
                    # Try to find the time in user input
                    for time in available_slots:
                        if time.lower() in message.lower():
                            selected_time = time
                            break
                    
                    if selected_time:
                        original_appointment_id = self.memory.booking_state.get("original_appointment_id")
                        selected_date = self.memory.booking_state.get("date")
                        
                        # Complete the rescheduling
                        return self._reschedule_appointment(original_appointment_id, selected_date, selected_time)
                    
                    # Time not found in available slots
                    slots_text = "\n- " + "\n- ".join(available_slots)
                    return f"Please select one of the following available time slots:{slots_text}"
                
                # For regular booking flow
                response = self._handle_booking(message, phone)
                
                # Store in memory but don't allow LLM to modify
                self.memory.add_message(message, response)
                return response
                
            # 3. Handle new booking requests
            if is_booking_request:
                print("Starting new booking flow")
                return self._handle_booking("start", phone)
                
            # 4. Handle view requests - only if there's a phone number
            if is_view_request and phone:
                print(f"Viewing appointments for phone: {phone}")
                return self._view_appointments(phone)
                
            # 5. Handle cancel/reschedule requests without appointment ID
            if is_cancel_request and not appointment_id:
                print("Cancel request without appointment ID")
                if phone:
                    return f"""To cancel an appointment, I need the appointment ID. Here are your appointments:\n\n{self._view_appointments(phone)}\n\nType 'cancel appointment appointment id'
                    for eg: cancel appointment APPT-20250505094214"""
                else:
                    return "To cancel an appointment, please provide your phone number and appointment ID."
                    
            if is_reschedule_request and not appointment_id:
                print("Reschedule request without appointment ID")
                if phone:
                    return f"""To reschedule an appointment, I need the appointment ID. Here are your appointments:\n\n{self._view_appointments(phone)}\n\nType 'reschedule appointment appointment id'
                    \n for eg: reschedule appointment APPT-20250505094214"""
                else:
                    return "To reschedule an appointment, please provide your phone number and appointment ID."
            
            # 6. For non-specified requests, use the general agent
            print("Using general agent")
            response = self.agent.run(message)
            
            # Store the conversation
            self.memory.add_message(message, response)
            
            return response
        except Exception as e:
            # Provide a meaningful error message
            print(f"ERROR in process_message: {str(e)}")
            traceback.print_exc()  # Print full exception traceback
            if self.memory.is_booking_active:
                self.memory.clear_booking_state()
                return "There was an error with the booking system. Please try again by saying 'book appointment'."
            else:
                return f"I apologize, but I encountered an error: {str(e)}. You can type 'reset' to clear my memory if I'm confused."

    def is_greeting(self, message: str) -> bool:
        """Check if the message is a greeting"""
        greetings = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", 
                     "good evening", "howdy", "hi there", "hello there", "namaste"]
        message = message.lower().strip()
        for greeting in greetings:
            if message.startswith(greeting) or message == greeting:
                return True
        return False

    def _store_patient_info(self, patient_info: str) -> str:
        """Store patient information in the database"""
        # In a real system, you'd use NER to extract structured information
        # Here we're simplifying with a more basic approach
        
        # Generate patient ID if we don't have one
        if not self.memory.current_patient_id:
            patient_id = f"patient_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self.memory.set_current_patient(patient_id)
        else:
            patient_id = self.memory.current_patient_id
        
        # Extract basic info - in production, use proper NLP
        info_dict = {"raw_info": patient_info}
        
        # Check for some common patterns
        if "name:" in patient_info.lower():
            name_parts = patient_info.lower().split("name:")[1].strip().split(" ")
            if len(name_parts) >= 2:
                info_dict["first_name"] = name_parts[0].capitalize()
                info_dict["last_name"] = name_parts[1].capitalize()
        
        if "dob:" in patient_info.lower() or "date of birth:" in patient_info.lower():
            # Extract DOB - in production use a proper date parser
            if "dob:" in patient_info.lower():
                dob_part = patient_info.lower().split("dob:")[1]
            else:
                dob_part = patient_info.lower().split("date of birth:")[1]
            
            # Assume format MM/DD/YYYY
            if "/" in dob_part:
                info_dict["dob"] = dob_part.strip().split(" ")[0]
        
        # Save to database
        existing_patient = self.database.get_patient(patient_id)
        if existing_patient:
            # Update existing record
            existing_patient.update(info_dict)
            self.database.add_patient(patient_id, existing_patient)
            return f"Patient information updated successfully."
        else:
            # Create new record
            self.database.add_patient(patient_id, info_dict)
            return f"New patient record created successfully."

# Example usage
if __name__ == "__main__":
    print("Initializing Medical Chatbot...")
    try:
        chatbot = MedicalChatbot()
        
        # Interactive mode
        print("Medical Chatbot Demo (type 'exit' to quit)")
        print("----------------------------------------")
        
        try:
            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("Chatbot: Thank you for using our medical chatbot service. Goodbye!")
                    break
                    
                response = chatbot.process_message(user_input)
                print(response['text'])
                print(f"Chatbot: {response}")
        except KeyboardInterrupt:
            print("\nExiting chatbot demo...")
    except Exception as e:
        print(f"Error initializing the chatbot: {e}")

user_sessions = {}
# Original MedicalChatbot class remains unchanged, just add this function
def get_or_create_user_bot(user_id):
    """Gets or creates a MedicalChatbot instance for a specific user"""
    if user_id not in user_sessions:
        bot = MedicalChatbot()
        # Dynamically bind the enhanced method to this bot instance
        bot.process_message = enhanced_process_message.__get__(bot)
        user_sessions[user_id] = bot
    return user_sessions[user_id]

# Override the process_message method to handle multiple user sessions
original_process_message = MedicalChatbot.process_message

def enhanced_process_message(self, message: str, phone: Optional[str] = None) -> str:
    """Enhanced process_message that formats responses for UI compatibility"""
    response = original_process_message(self, message, phone)
    return response

# Apply the monkey patch
MedicalChatbot.process_message = enhanced_process_message