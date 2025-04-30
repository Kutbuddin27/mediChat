# Medical Chatbot with LangChain using Google Generative AI
# Features: Document Handling, Prompt Management, Memory, Integrations

import os
from typing import Dict, List, Any
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

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
                input_variables=["name"],
                template="Hello {name}, I'm your medical assistant. How can I help you today?"
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
    
    def get_available_slots(self, doctor_id: str, date: str) -> List[str]:
        """Get available appointment slots for a specific doctor on a specific date"""
        # In a real system, this would be more sophisticated
        all_slots = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]
        booked_slots = []
        
        for _, appt in self.data["appointments"].items():
            if appt.get("doctor_id") == doctor_id and appt.get("date") == date:
                booked_slots.append(appt.get("time"))
        
        available_slots = [slot for slot in all_slots if slot not in booked_slots]
        return available_slots

    def save_partial_patient_data(self, patient_id: str, data: dict):
        if patient_id not in self.data["patients"]:
            self.data["patients"][patient_id] = {}
        self.data["patients"][patient_id].update(data)


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
                name="Look Up Patient",
                func=self._get_patient_info,
                description="Use this to look up information about a specific patient"
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

    def _validate_state_for_step(self, step: str, state: dict) -> bool:
        if step == "select_date":
            return "doctor_id" in state
        if step == "select_time":
            return "doctor_id" in state and "date" in state
        if step == "collect_name":
            return all(k in state for k in ["doctor_id", "date", "time"])
        if step == "collect_phone":
            return "name" in state
        if step == "confirm":
            return all(k in state for k in ["name", "phone", "doctor_id", "date", "time"])
        return True

    def _format_doctor_list(self, doctors: dict, doctor_options: dict) -> str:
        doctor_list = []
        for option, doc_id in doctor_options.items():
            doc_info = doctors[doc_id]
            doctor_list.append(f"{option}. {doc_info['name']} ({doc_info['specialty']})")
        formatted_list = "\n".join(doctor_list)
        return f"Okay! We have the following doctors available:\n\n{formatted_list}\n\nPlease select a doctor by typing the corresponding letter."

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
                
    def _handle_booking(self, input_text: str) -> str:
        """Handle appointment booking workflow with strict hardcoded flow"""
        # Check for direct booking start
        if input_text.lower() == "start" or any(keyword in input_text.lower() for keyword in ["book", "appointment", "schedule", "see a doctor"]):
            # Clear any existing booking state to start fresh
            self.memory.clear_booking_state()
            self.memory.start_booking_flow()
            
            # Log the start of a new booking
            print(f"Starting new booking flow at {datetime.now()}")
            
            # Get doctor list from database
            doctors = self.database.data["doctors"]
            options = {chr(65 + i): doc_id for i, doc_id in enumerate(doctors)}
            self.memory.update_booking_state(doctor_options=options, step="select_doctor")
            
            # HARDCODED response for doctor selection
            doctor_list = []
            for option, doc_id in options.items():
                doc_info = doctors[doc_id]
                doctor_list.append(f"{option}. Dr. {doc_info['name']} ({doc_info['specialty']})")
            
            formatted_list = "\n".join(doctor_list)
            return f"Let's book your appointment. Please select a doctor by typing the corresponding letter:\n\n{formatted_list}"
        
        # Check if we have an active booking flow
        if not self.memory.is_booking_active:
            # This should not happen with our new flow control
            self.memory.start_booking_flow()
            
            # Log the start of a new booking
            print(f"WARNING: Booking function called without active flow. Starting at {datetime.now()}")
            
            doctors = self.database.data["doctors"]
            options = {chr(65 + i): doc_id for i, doc_id in enumerate(doctors)}
            self.memory.update_booking_state(doctor_options=options, step="select_doctor")
            
            # HARDCODED doctor selection prompt
            doctor_list = []
            for option, doc_id in options.items():
                doc_info = doctors[doc_id]
                doctor_list.append(f"{option}. Dr. {doc_info['name']} ({doc_info['specialty']})")
            
            formatted_list = "\n".join(doctor_list)
            return f"Let's book your appointment. Please select a doctor by typing the corresponding letter:\n\n{formatted_list}"
        
        # Log the current state and input for debugging
        booking_state = self.memory.booking_state
        print(f"Current booking state: {json.dumps(booking_state)}")
        print(f"User input: {input_text}")
        
        # Get current step from state
        step = booking_state.get("step")
        
        # STRICTLY SEQUENTIAL FLOW with hardcoded responses for each step
        if step == "select_doctor":
            # Check if user entered an option letter
            input_letter = input_text.strip().upper()
            doctor_options = booking_state.get("doctor_options", {})
            
            # Try to match by letter
            if input_letter in doctor_options:
                doc_id = doctor_options[input_letter]
                doc_info = self.database.data["doctors"][doc_id]
                
                self.memory.update_booking_state(doctor_id=doc_id, step="select_date")
                
                # HARDCODED date selection prompt
                tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                next_day = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
                next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                return f"When would you like to book your appointment with Dr. {doc_info['name']}?\n\nAvailable dates are:\n- {tomorrow}\n- {next_day}\n- {next_week}\n\nPlease provide a date in YYYY-MM-DD format."
            
            # Try to match by doctor name
            for doc_id, doc_info in self.database.data["doctors"].items():
                if doc_info["name"].lower() in input_text.lower():
                    self.memory.update_booking_state(doctor_id=doc_id, step="select_date")
                    
                    # HARDCODED date selection prompt
                    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                    next_day = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
                    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                    return f"When would you like to book your appointment with Dr. {doc_info['name']}?\n\nAvailable dates are:\n- {tomorrow}\n- {next_day}\n- {next_week}\n\nPlease provide a date in YYYY-MM-DD format."
            
            # Neither option letter nor doctor name matched
            # HARDCODED doctor selection retry prompt
            doctors = self.database.data["doctors"]
            options = booking_state.get("doctor_options", {})
            doctor_list = []
            for option, doc_id in options.items():
                doc_info = doctors[doc_id]
                doctor_list.append(f"{option}. Dr. {doc_info['name']} ({doc_info['specialty']})")
            
            formatted_list = "\n".join(doctor_list)
            return f"I couldn't identify which doctor you'd like to see. Please select from the options below by entering the letter:\n\n{formatted_list}"
        
        elif step == "select_date":
            # Simple date extraction
            if '-' in input_text and len(input_text.split('-')) == 3:
                selected_date = input_text.strip()
                doctor_id = booking_state.get("doctor_id")
                doctor_name = self.database.data["doctors"][doctor_id]["name"]
                
                # HARDCODED time slots
                available_slots = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]
                slots_text = "\n- " + "\n- ".join(available_slots)
                
                self.memory.update_booking_state(date=selected_date, step="select_time")
                
                # HARDCODED time selection prompt
                return f"For {selected_date} with Dr. {doctor_name}, we have the following slots available:{slots_text}\n\nWhat time works for you?"
            
            # HARDCODED date format error prompt
            return "Please provide a date in the format YYYY-MM-DD (for example, 2025-04-24)."
        
        elif step == "select_time":
            # Fixed time slots
            common_times = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]
            selected_time = None
            
            # Try to find the time in user input
            for time in common_times:
                if time.lower() in input_text.lower():
                    selected_time = time
                    break
            
            if selected_time:
                self.memory.update_booking_state(time=selected_time, step="collect_name")
                
                # HARDCODED name collection prompt
                return "Please enter your full name for booking:📄 "
            
            # HARDCODED time selection retry prompt
            slots_text = "\n- " + "\n- ".join(common_times)
            return f"Please select one of the following slots available time slots:{slots_text}"
        
        elif step == "collect_name":
            name = input_text.strip()
            if not name:
                # HARDCODED name error prompt
                return "Your name is required. Please enter your full name:"
            
            self.memory.update_booking_state(name=name, step="collect_phone")
            
            # Save partial patient data
            patient_id = self.memory.current_patient_id or f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self.memory.set_current_patient(patient_id)
            self.database.save_partial_patient_data(patient_id, {"name": name})
            
            # HARDCODED phone collection prompt
            return "Okay Please enter your phone number also📝:"
        elif step == "collect_phone":
            phone = input_text.strip()
            if not phone:
                # HARDCODED phone error prompt
                return "Your phone number is required. Please enter your phone number📝:"
            
            self.memory.update_booking_state(phone=phone, step="confirm")
            
            # Update patient record with phone
            patient_id = self.memory.current_patient_id
            self.database.save_partial_patient_data(patient_id, {"phone": phone})
            
            # HARDCODED reason collection prompt
            return "Lastly Please provide the reason for your visit to confirm your Appointment"
        
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
                "status": "confirmed"
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
            
            # Clear booking state after successful save
            self.memory.clear_booking_state()
            
            # HARDCODED confirmation message with all details in a standardized format
            return f"""Appointment Successfully Booked!🎉 

        Appointment ID: {appointment_id}
        Patient: {name}
        Doctor: Dr. {doctor_name}
        Date: {booking_state.get("date")}
        Time: {booking_state.get("time")}
        Phone: {phone}
        Reason: {reason}

        Thank you for booking with us. You will receive a confirmation text message shortly. If you need to reschedule or cancel, please contact us and reference your Appointment ID."""
        
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
    
    def _get_patient_info(self, patient_identifier: str) -> str:
        """Look up patient information"""
        # In a real system, you'd have better search capabilities
        if self.memory.current_patient_id:
            patient_data = self.database.get_patient(self.memory.current_patient_id)
            if patient_data:
                # Format patient data
                formatted_data = []
                for key, value in patient_data.items():
                    if key != "raw_info":  # Skip the raw info field
                        formatted_data.append(f"{key}: {value}")
                
                return "Patient information:\n" + "\n".join(formatted_data)
        
        return "I'm sorry, I couldn't find patient information. Please provide patient details first."
    
    def process_message(self, message: str) -> str:
        """Process an incoming message with booking flow override"""
        try:
            # Check for reset command
            if message.lower().strip() in ["reset", "clear memory", "restart", "clear cache"]:
                return self.reset_conversation()
            
            # Check for booking-specific reset
            if message.lower().strip() in ["cancel booking", "stop booking"]:
                self.memory.clear_booking_state()
                return "Booking process canceled. How else can I help you today?"
            
            # Check for booking intent keywords
            booking_keywords = ["book", "appointment", "schedule", "see a doctor", "visit"]
            is_booking_request = any(keyword in message.lower() for keyword in booking_keywords)
            
            # If booking is active or this is a new booking request
            if self.memory.is_booking_active or is_booking_request:
                # If this is a new booking request and we're not already in a booking flow
                if is_booking_request and not self.memory.is_booking_active:
                    # Start booking flow directly
                    return self._handle_booking("start")
                
                # If already in booking flow, continue with hardcoded flow
                if self.memory.is_booking_active:
                    response = self._handle_booking(message)
                    
                    # Store in memory but don't allow LLM to modify
                    self.memory.add_message(message, response)
                    return response
            
            # For non-booking related queries, use the agent
            response = self.agent.run(message)
            
            # Store the conversation
            self.memory.add_message(message, response)
            
            return response
        except Exception as e:
            # Provide a meaningful error message
            print(f"ERROR in process_message: {str(e)}")
            if self.memory.is_booking_active:
                self.memory.clear_booking_state()
                return "There was an error with the booking system. Please try again by saying 'book appointment'."
            else:
                return f"I apologize, but I encountered an error: {str(e)}. You can type 'reset' to clear my memory if I'm confused."

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

def enhanced_process_message(self, message):
    """Enhanced process_message that formats responses for UI compatibility"""
    response = original_process_message(self, message)

    return response

# Apply the monkey patch
MedicalChatbot.process_message = enhanced_process_message