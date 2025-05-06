def _handle_booking(self, input_text: str, phone: Optional[str] = None) -> str:
    """Handle appointment booking workflow with duplicate prevention"""
    # Check for direct booking start
    if input_text.lower() == "start" or any(keyword in input_text.lower() for keyword in ["book", "appointment", "schedule", "see a doctor"]):
        # Clear any existing booking state to start fresh
        self.memory.clear_booking_state()
        self.memory.start_booking_flow()
        
        # Log the start of a new booking
        print(f"Starting new booking flow at {datetime.now()}")
        
        # STEP 1: Start with specialty selection
        # Get specialties with available doctors
        doctors = self.database.data["doctors"]
        appointments = self.database.data.get("appointments", {})
        
        # Track which doctors have availability
        available_doctors = {}
        for doc_id, doc_info in doctors.items():
            # Check if this doctor has any available slots
            has_slots = False
            
            # Check the next 14 days
            current_date = datetime.now().date()
            for day_offset in range(1, 15):
                date_str = (current_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                
                # Check each time slot
                for time_slot in ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM"]:
                    # See if this slot is booked
                    is_booked = False
                    for _, appt in appointments.items():
                        if (appt.get("doctor_id") == doc_id and 
                            appt.get("date") == date_str and 
                            appt.get("time") == time_slot and
                            appt.get("status") != "cancelled"):
                            is_booked = True
                            break
                    
                    if not is_booked:
                        has_slots = True
                        available_doctors[doc_id] = doc_info
                        break
                
                if has_slots:
                    break
        
        # Get unique specialties from available doctors
        specialties = set(doc_info["specialty"] for doc_id, doc_info in available_doctors.items())
        
        if not specialties:
            return "We're sorry, but all doctors are fully booked at this time. Please try again later or contact our office directly for assistance."
        
        specialty_options = {chr(65 + i): specialty for i, specialty in enumerate(sorted(specialties))}
        
        self.memory.update_booking_state(
            specialty_options=specialty_options, 
            step="select_specialty",
            available_doctors=available_doctors
        )
        
        # HARDCODED response for specialty selection
        specialty_list = []
        for option, specialty in specialty_options.items():
            specialty_list.append(f"{option}. {specialty}")
        
        formatted_list = "\n".join(specialty_list)
        return f"Let's book your appointment. First, please select a medical specialty by typing the corresponding letter:\n\n{formatted_list}"
    
    # Check if we have an active booking flow
    if not self.memory.is_booking_active:
        # Start a new booking flow (same code as above)
        self.memory.start_booking_flow()
        
        # Log the start of a new booking
        print(f"WARNING: Booking function called without active flow. Starting at {datetime.now()}")
        
        # STEP 1: Start with specialty selection
        # Get specialties with available doctors
        doctors = self.database.data["doctors"]
        appointments = self.database.data.get("appointments", {})
        
        # Track which doctors have availability
        available_doctors = {}
        for doc_id, doc_info in doctors.items():
            # Check if this doctor has any available slots
            has_slots = False
            
            # Check the next 14 days
            current_date = datetime.now().date()
            for day_offset in range(1, 15):
                date_str = (current_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                
                # Check each time slot
                for time_slot in ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM"]:
                    # See if this slot is booked
                    is_booked = False
                    for _, appt in appointments.items():
                        if (appt.get("doctor_id") == doc_id and 
                            appt.get("date") == date_str and 
                            appt.get("time") == time_slot and
                            appt.get("status") != "cancelled"):
                            is_booked = True
                            break
                    
                    if not is_booked:
                        has_slots = True
                        available_doctors[doc_id] = doc_info
                        break
                
                if has_slots:
                    break
        
        # Get unique specialties from available doctors
        specialties = set(doc_info["specialty"] for doc_id, doc_info in available_doctors.items())
        
        if not specialties:
            return "We're sorry, but all doctors are fully booked at this time. Please try again later or contact our office directly for assistance."
        
        specialty_options = {chr(65 + i): specialty for i, specialty in enumerate(sorted(specialties))}
        
        self.memory.update_booking_state(
            specialty_options=specialty_options, 
            step="select_specialty",
            available_doctors=available_doctors
        )
        
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
    
    # SEQUENTIAL FLOW with hardcoded responses for each step
    # STEP: Select specialty
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
            # Filter doctors by selected specialty AND availability
            available_doctors = booking_state.get("available_doctors", {})
            filtered_doctors = {doc_id: doc_info for doc_id, doc_info in available_doctors.items() 
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
                doc_info = filtered_doctors[doc_id]
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
        appointments = self.database.data.get("appointments", {})
        
        # Try to match by letter
        selected_doctor_id = None
        if input_letter in doctor_options:
            selected_doctor_id = doctor_options[input_letter]
        
        # Try to match by doctor name
        if not selected_doctor_id:
            for doc_id in doctor_options.values():
                doc_info = self.database.data["doctors"][doc_id]
                if doc_info["name"].lower() in input_text.lower():
                    selected_doctor_id = doc_id
                    break
        
        if selected_doctor_id:
            doc_info = self.database.data["doctors"][selected_doctor_id]
            
            # Find available dates for this doctor
            available_dates = []
            current_date = datetime.now().date()
            
            # Check the next 14 days
            for day_offset in range(1, 15):
                date_str = (current_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                
                # Check if at least one slot is available on this date
                has_slot = False
                for time_slot in ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM"]:
                    # See if this slot is booked
                    is_booked = False
                    for _, appt in appointments.items():
                        if (appt.get("doctor_id") == selected_doctor_id and 
                            appt.get("date") == date_str and 
                            appt.get("time") == time_slot and
                            appt.get("status") != "cancelled"):
                            is_booked = True
                            break
                    
                    if not is_booked:
                        has_slot = True
                        break
                
                if has_slot:
                    available_dates.append(date_str)
            
            if not available_dates:
                return f"I apologize, but Dr. {doc_info['name']} has no available appointments at this time. Please select another doctor."
            
            # Create date options
            date_options = {chr(65 + i): date_str for i, date_str in enumerate(available_dates)}
            
            self.memory.update_booking_state(
                doctor_id=selected_doctor_id, 
                step="select_date",
                date_options=date_options
            )
            
            # Format dates for display
            date_list = []
            for option, date_str in date_options.items():
                # Try to format the date nicely if possible
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%A, %B %d, %Y")
                    date_list.append(f"{option}. {formatted_date} ({date_str})")
                except:
                    date_list.append(f"{option}. {date_str}")
            
            formatted_list = "\n".join(date_list)
            return f"When would you like to book your appointment with Dr. {doc_info['name']}?\n\nAvailable dates:\n{formatted_list}\n\nPlease select by letter or date (YYYY-MM-DD format)."
        
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
        date_options = booking_state.get("date_options", {})
        doctor_id = booking_state.get("doctor_id")
        doctor_name = self.database.data["doctors"][doctor_id]["name"]
        appointments = self.database.data.get("appointments", {})
        
        # Check if user entered a letter or a date
        selected_date = None
        input_letter = input_text.strip().upper()
        
        # Try to match by letter
        if input_letter in date_options:
            selected_date = date_options[input_letter]
        
        # Try to match by date format
        elif '-' in input_text and len(input_text.split('-')) == 3:
            entered_date = input_text.strip()
            # Verify it's one of our available dates
            if entered_date in date_options.values():
                selected_date = entered_date
            else:
                # Not an available date, show options again
                date_list = []
                for option, date_str in date_options.items():
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        formatted_date = date_obj.strftime("%A, %B %d, %Y")
                        date_list.append(f"{option}. {formatted_date} ({date_str})")
                    except:
                        date_list.append(f"{option}. {date_str}")
                
                formatted_list = "\n".join(date_list)
                return f"I'm sorry, but {entered_date} is not available with Dr. {doctor_name}. Please select from these available dates:\n\n{formatted_list}"
        
        if selected_date:
            # Find available morning and evening slots
            available_morning = []
            for time_slot in ["9:00 AM", "10:00 AM", "11:00 AM"]:
                is_booked = False
                for _, appt in appointments.items():
                    if (appt.get("doctor_id") == doctor_id and 
                        appt.get("date") == selected_date and 
                        appt.get("time") == time_slot and
                        appt.get("status") != "cancelled"):
                        is_booked = True
                        break
                
                if not is_booked:
                    available_morning.append(time_slot)
            
            available_evening = []
            for time_slot in ["1:00 PM", "2:00 PM", "3:00 PM"]:
                is_booked = False
                for _, appt in appointments.items():
                    if (appt.get("doctor_id") == doctor_id and 
                        appt.get("date") == selected_date and 
                        appt.get("time") == time_slot and
                        appt.get("status") != "cancelled"):
                        is_booked = True
                        break
                
                if not is_booked:
                    available_evening.append(time_slot)
            
            # Update booking state
            self.memory.update_booking_state(
                date=selected_date,
                available_morning=available_morning,
                available_evening=available_evening
            )
            
            # Check what time options we have
            if not available_morning and not available_evening:
                # This shouldn't happen due to our filtering
                return f"I apologize, but there are no available time slots for Dr. {doctor_name} on {selected_date}. Please select another date."
            
            elif available_morning and available_evening:
                # Both morning and evening available
                self.memory.update_booking_state(step="select_time_preference")
                return f"For your appointment with Dr. {doctor_name} on {selected_date}, do you prefer a morning or evening slot? Please type 'morning' or 'evening'."
            
            elif available_morning:
                # Only morning available
                self.memory.update_booking_state(time_preference="morning", step="select_time")
                slots_text = "\n- " + "\n- ".join(available_morning)
                return f"For {selected_date} with Dr. {doctor_name}, we have the following morning slots available:{slots_text}\n\nWhat time works for you?"
            
            else:
                # Only evening available
                self.memory.update_booking_state(time_preference="evening", step="select_time")
                slots_text = "\n- " + "\n- ".join(available_evening)
                return f"For {selected_date} with Dr. {doctor_name}, we have the following evening slots available:{slots_text}\n\nWhat time works for you?"
        
        # HARDCODED date format or selection error prompt
        date_list = []
        for option, date_str in date_options.items():
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%A, %B %d, %Y")
                date_list.append(f"{option}. {formatted_date} ({date_str})")
            except:
                date_list.append(f"{option}. {date_str}")
        
        formatted_list = "\n".join(date_list)
        return f"Please select one of the available dates by entering its letter or in YYYY-MM-DD format:\n\n{formatted_list}"
    
    # Time preference step
    elif step == "select_time_preference":
        preference = input_text.strip().lower()
        doctor_id = booking_state.get("doctor_id")
        doctor_name = self.database.data["doctors"][doctor_id]["name"]
        selected_date = booking_state.get("date")
        
        # Get the stored available slots
        available_morning = booking_state.get("available_morning", [])
        available_evening = booking_state.get("available_evening", [])
        
        if "morning" in preference and available_morning:
            # Morning slots
            self.memory.update_booking_state(time_preference="morning", step="select_time")
            slots_text = "\n- " + "\n- ".join(available_morning)
            return f"🌞For {selected_date} with Dr. {doctor_name}, we have the following morning slots available:{slots_text}\n\nWhat time works for you?"
            
        elif "evening" in preference and available_evening:
            # Evening slots
            self.memory.update_booking_state(time_preference="evening", step="select_time")
            slots_text = "\n- " + "\n- ".join(available_evening)
            return f"🌞For {selected_date} with Dr. {doctor_name}, we have the following evening slots available:{slots_text}\n\nWhat time works for you?"
            
        else:
            # If preference not clear or not available, ask again
            prompt_parts = ["Please specify if you prefer a"]
            if available_morning:
                prompt_parts.append("morning")
            if available_morning and available_evening:
                prompt_parts.append("or")
            if available_evening:
                prompt_parts.append("evening")
            prompt_parts.append("appointment.")
            
            return " ".join(prompt_parts)
    
    elif step == "select_time":
        # Get time preference from booking state
        time_preference = booking_state.get("time_preference", "")
        
        # Get the stored available slots based on preference
        if time_preference == "morning":
            available_times = booking_state.get("available_morning", [])
        elif time_preference == "evening":
            available_times = booking_state.get("available_evening", [])
        else:
            # Combine both if somehow preference is missing
            available_times = booking_state.get("available_morning", []) + booking_state.get("available_evening", [])
        
        selected_time = None
        
        # Try to find the time in user input
        for time in available_times:
            if time.lower() in input_text.lower():
                selected_time = time
                break
        
        if selected_time:
            self.memory.update_booking_state(time=selected_time, step="collect_name")
            
            # HARDCODED name collection prompt
            return "Please enter your full name for booking:📄 "
        
        # HARDCODED time selection retry prompt with only relevant slots
        slots_text = "\n- " + "\n- ".join(available_times)
        doctor_id = booking_state.get("doctor_id")
        doctor_name = self.database.data["doctors"][doctor_id]["name"]
        selected_date = booking_state.get("date")
        return f"🌞Please select one of the following available time slots for Dr. {doctor_name} on {selected_date}:{slots_text}"
    
    elif step == "collect_name":
        name = input_text.strip()
        if not name:
            return "Your name is required. Please enter your full name:"

        self.memory.update_booking_state(name=name)

        patient_id = self.memory.current_patient_id or f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.memory.set_current_patient(patient_id)
        self.database.save_partial_patient_data(patient_id, {"name": name})

        if phone:
            self.memory.update_booking_state(phone=phone, step="confirm")
            self.database.save_partial_patient_data(patient_id, {"phone": phone})
            return "Lastly, please provide the reason for your visit to confirm your appointment."
        else:
            self.memory.update_booking_state(step="collect_phone")
            return "Okay, please enter your phone number also 📝:"

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
            "status": "confirmed",
            "specialty": booking_state.get("selected_specialty")  # Store the specialty
        }
        
        # Validate required fields
        missing_fields = [f for f in ["doctor_id", "date", "time"] if not appointment_data.get(f)]
        if missing_fields:
            self.memory.clear_booking_state()
            # HARDCODED missing fields prompt
            return "Missing appointment details. Booking process has been reset. Please try again by asking to book an appointment."
        
        # One final check to make sure this time slot is still available
        doctor_id = booking_state.get("doctor_id")
        date = booking_state.get("date")
        time = booking_state.get("time")
        appointments = self.database.data.get("appointments", {})
        
        # Check if this slot is already booked
        for _, appt in appointments.items():
            if (appt.get("doctor_id") == doctor_id and 
                appt.get("date") == date and 
                appt.get("time") == time and
                appt.get("status") != "cancelled"):
                self.memory.clear_booking_state()
                return "We're sorry, but this time slot has just been booked by another patient. Please start the booking process again."
        
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
    Date: {date}
    Time: {time}
    Phone: {phone}
    Reason: {reason}

    Thank you for booking with us. You will receive a confirmation text message shortly. If you need to reschedule or cancel, please contact us and reference your Appointment ID."""