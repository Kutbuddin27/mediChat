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
from langchain.prompts import PromptTemplate
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
    def __init__(self, db_path: str = "medical_database.json"):
        self.db_path = db_path
        self.data = self._load_db()
    
    def _load_db(self) -> Dict:
        """Load the database from file or create a new one"""
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                return json.load(f)
        else:
            # Initialize with sample data
            data = {
                "patients": {},
                "appointments": {},
                "doctors": {
                    "dr_smith": {"name": "Dr. Smith", "specialty": "General Practice"},
                    "dr_jones": {"name": "Dr. Jones", "specialty": "Cardiology"},
                    "dr_patel": {"name": "Dr. Patel", "specialty": "Pediatrics"}
                }
            }
            self._save_db(data)
            return data
    
    def _save_db(self, data=None):
        """Save the current database to file"""
        if data is None:
            data = self.data
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_patient(self, patient_id: str, patient_data: Dict) -> bool:
        """Add a new patient to the database"""
        if patient_id in self.data["patients"]:
            return False  # Patient already exists
        
        self.data["patients"][patient_id] = patient_data
        self._save_db()
        return True
    
    def get_patient(self, patient_id: str) -> Dict:
        """Get patient information"""
        return self.data["patients"].get(patient_id, {})
    
    def book_appointment(self, appointment_id: str, appointment_data: Dict) -> bool:
        """Book a new appointment"""
        if appointment_id in self.data["appointments"]:
            return False  # Appointment ID already exists
        
        self.data["appointments"][appointment_id] = appointment_data
        self._save_db()
        return True
    
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


# ---- Memory Component ----
class MedicalChatMemory:
    def __init__(self):
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        self.current_patient_id = None
        self.booking_state = {}
    
    def add_message(self, human_message: str, ai_message: str):
        """Add a message pair to memory"""
        self.memory.chat_memory.add_user_message(human_message)
        self.memory.chat_memory.add_ai_message(ai_message)
    
    def get_chat_history(self) -> str:
        """Get formatted chat history"""
        return self.memory.load_memory_variables({})["chat_history"]
    
    def set_current_patient(self, patient_id: str):
        """Set the current patient context"""
        self.current_patient_id = patient_id
    
    def start_booking_flow(self, doctor_id: str = None):
        """Start an appointment booking flow"""
        self.booking_state = {
            "in_progress": True,
            "step": "select_doctor",
            "doctor_id": doctor_id,
            "date": None,
            "time": None,
            "reason": None
        }
    
    def update_booking_state(self, **kwargs):
        """Update the current booking state"""
        self.booking_state.update(kwargs)
    
    def clear_booking_state(self):
        """Clear the booking flow state"""
        self.booking_state = {}


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
        
        prompt = self.prompt_manager.get_prompt(
            "medical_query",
            query=query,
            context=context
        )
        
        # In a real system, you'd process this through the LLM
        # Here we'll simulate a response
        return f"Based on our medical knowledge: {context[:200]}..."
    
    def _handle_booking(self, input_text: str) -> str:
        """Handle appointment booking workflow"""
        # If no booking in progress, start one
        if not self.memory.booking_state.get("in_progress", False):
            self.memory.start_booking_flow()
            
            # Get list of doctors
            doctors = self.database.data["doctors"]
            doctor_list = ", ".join([f"{d['name']} ({d['specialty']})" for d in doctors.values()])
            
            return f"Let's book an appointment. We have the following doctors available: {doctor_list}. Which doctor would you like to see?"
        
        # Process booking flow based on current step
        booking_state = self.memory.booking_state
        step = booking_state.get("step")
        
        if step == "select_doctor":
            # Extract doctor from input (in production, use NLU)
            for doc_id, doc_info in self.database.data["doctors"].items():
                if doc_info["name"].lower() in input_text.lower():
                    self.memory.update_booking_state(doctor_id=doc_id, step="select_date")
                    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                    next_day = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
                    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                    return f"When would you like to book your appointment with {doc_info['name']}? We have availability on {tomorrow}, {next_day}, and {next_week}."
            
            return "I'm sorry, I couldn't identify which doctor you'd like to see. Could you please specify the doctor's name clearly?"
        
        elif step == "select_date":
            # Simple date extraction (in production, use proper date parsing)
            # Use a date in the format YYYY-MM-DD
            if '-' in input_text:
                date_parts = input_text.split('-')
                if len(date_parts) == 3:
                    selected_date = input_text.strip()
                    doctor_id = booking_state.get("doctor_id")
                    doctor_name = self.database.data["doctors"][doctor_id]["name"]
                    
                    available_slots = self.database.get_available_slots(doctor_id, selected_date)
                    if not available_slots:
                        return f"I'm sorry, there are no available slots for {doctor_name} on {selected_date}. Would you like to try another date?"
                    
                    slots_text = ", ".join(available_slots)
                    self.memory.update_booking_state(date=selected_date, step="select_time")
                    return f"For {selected_date} with {doctor_name}, we have the following slots available: {slots_text}. What time works for you?"
            
            return "Please provide a date in the format YYYY-MM-DD, such as 2025-04-24."
        
        elif step == "select_time":
            # Extract time (in production, use better time parsing)
            common_times = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]
            selected_time = None
            
            for time in common_times:
                if time.lower() in input_text.lower():
                    selected_time = time
                    break
            
            if selected_time:
                self.memory.update_booking_state(time=selected_time, step="confirm")
                doctor_id = booking_state.get("doctor_id")
                date = booking_state.get("date")
                doctor_name = self.database.data["doctors"][doctor_id]["name"]
                
                return f"You're booking an appointment with {doctor_name} on {date} at {selected_time}. What is the reason for your visit?"
            
            return "Please select one of the available time slots mentioned earlier."
        
        elif step == "confirm":
            # Store the reason for visit and confirm booking
            self.memory.update_booking_state(reason=input_text, step="complete")
            
            # Generate appointment ID
            appointment_id = f"appt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create appointment data
            appointment_data = {
                "doctor_id": booking_state.get("doctor_id"),
                "patient_id": self.memory.current_patient_id or "unknown_patient",
                "date": booking_state.get("date"),
                "time": booking_state.get("time"),
                "reason": booking_state.get("reason"),
                "status": "confirmed"
            }
            
            # Store in database
            self.database.book_appointment(appointment_id, appointment_data)
            
            doctor_name = self.database.data["doctors"][booking_state.get("doctor_id")]["name"]
            self.memory.clear_booking_state()
            
            return f"Your appointment with {doctor_name} on {appointment_data['date']} at {appointment_data['time']} has been confirmed. Your appointment ID is {appointment_id}. We look forward to seeing you!"
        
        return "I'm sorry, there was an issue with the booking process. Please try again."
    
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
        """Process an incoming message and generate a response"""
        try:
            # Use the agent to determine the appropriate action
            response = self.agent.run(message)
            
            # Store the conversation
            self.memory.add_message(message, response)
            
            return response
        except Exception as e:
            # Provide a meaningful error message
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"


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
                print(f"Chatbot: {response}")
        except KeyboardInterrupt:
            print("\nExiting chatbot demo...")
    except Exception as e:
        print(f"Error initializing the chatbot: {e}")

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