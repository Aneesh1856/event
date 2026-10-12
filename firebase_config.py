import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import os
import time

# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase with service account credentials"""
    try:
        # Check if Firebase is already initialized
        if not firebase_admin._apps:
            cred = None
            
            # Method 1: Try environment variable first (for production)
            firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
            if firebase_creds_json:
                try:
                    import json
                    creds_dict = json.loads(firebase_creds_json)
                    cred = credentials.Certificate(creds_dict)
                    print("✅ Using Firebase credentials from environment variable")
                except Exception as env_error:
                    print(f"❌ Error parsing Firebase credentials from environment: {env_error}")
            
            # Method 2: Try credentials file (for local development)
            if not cred:
                credentials_file = "firebase-credentials.json"
                if os.path.exists(credentials_file):
                    try:
                        cred = credentials.Certificate(credentials_file)
                        print("✅ Using Firebase credentials from file")
                    except Exception as file_error:
                        print(f"❌ Error loading Firebase credentials from file: {file_error}")
                else:
                    print(f"❌ Firebase credentials file '{credentials_file}' not found!")
            
            # If no credentials found
            if not cred:
                print("❌ No valid Firebase credentials found!")
                print("Please follow the instructions in FIREBASE_FIX_INSTRUCTIONS.md")
                return None
            
            # Initialize the app with a service account, granting admin privileges
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://event-fe792-default-rtdb.firebaseio.com/'
            })
            
            print("✅ Firebase initialized successfully!")
        
        return db.reference()
    
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        if "Invalid JWT Signature" in str(e) or "invalid_grant" in str(e):
            print("🔧 This appears to be a credentials issue.")
            print("Please regenerate your Firebase service account credentials.")
            print("See FIREBASE_FIX_INSTRUCTIONS.md for detailed instructions.")
        return None

# Firebase Database Helper Functions
class FirebaseDB:
    def __init__(self):
        self.ref = initialize_firebase()
        self._cache = {}
        self._cache_expiry = {}

    def _get_cache(self, key):
        """Retrieve cached data if within TTL"""
        now = time.time()
        if key in self._cache and now < self._cache_expiry.get(key, 0):
            return self._cache[key]
        return None

    def _set_cache(self, key, value, ttl=30):
        """Store data in memory cache with TTL in seconds"""
        self._cache[key] = value
        self._cache_expiry[key] = time.time() + ttl

    def invalidate_cache(self, *keys):
        """Invalidate specified cache keys or all if none given"""
        if not keys:
            self._cache.clear()
            self._cache_expiry.clear()
        else:
            for k in keys:
                self._cache.pop(k, None)
                self._cache_expiry.pop(k, None)
    
    def save_teacher(self, teacher_id, teacher_data):
        """Save teacher data to Firebase"""
        try:
            teachers_ref = self.ref.child('teachers')
            teachers_ref.child(teacher_id).set(teacher_data)
            self.invalidate_cache('teachers')
            return True
        except Exception as e:
            print(f"Error saving teacher: {e}")
            return False

    # Event Management Functions
    def save_event_organizer(self, organizer_id, organizer_data):
        """Save event organizer data to Firebase"""
        try:
            organizers_ref = self.ref.child('event_organizers')
            organizers_ref.child(organizer_id).set(organizer_data)
            self.invalidate_cache('event_organizers', f'org_{organizer_id}')
            return True
        except Exception as e:
            print(f"Error saving event organizer: {e}")
            return False

    def get_event_organizer(self, organizer_id):
        """Get event organizer data from Firebase"""
        cached = self._get_cache(f'org_{organizer_id}')
        if cached is not None:
            return cached
        try:
            organizer_ref = self.ref.child('event_organizers').child(organizer_id)
            data = organizer_ref.get()
            if data is not None:
                self._set_cache(f'org_{organizer_id}', data, ttl=45)
            return data
        except Exception as e:
            print(f"Error getting event organizer: {e}")
            return None

    def get_all_event_organizers(self):
        """Get all event organizers from Firebase"""
        cached = self._get_cache('event_organizers')
        if cached is not None:
            return cached
        try:
            organizers_ref = self.ref.child('event_organizers')
            data = organizers_ref.get() or {}
            self._set_cache('event_organizers', data, ttl=30)
            return data
        except Exception as e:
            print(f"Error getting all event organizers: {e}")
            return {}

    def save_event(self, event_id, event_data):
        """Save event data to Firebase"""
        try:
            events_ref = self.ref.child('events')
            events_ref.child(event_id).set(event_data)
            self.invalidate_cache('events', f'event_{event_id}')
            return True
        except Exception as e:
            print(f"Error saving event: {e}")
            return False

    def get_event(self, event_id):
        """Get event data from Firebase"""
        cached = self._get_cache(f'event_{event_id}')
        if cached is not None:
            return cached
        try:
            event_ref = self.ref.child('events').child(event_id)
            data = event_ref.get()
            if data is not None:
                self._set_cache(f'event_{event_id}', data, ttl=30)
            return data
        except Exception as e:
            print(f"Error getting event: {e}")
            return None

    def get_all_events(self):
        """Get all events from Firebase"""
        cached = self._get_cache('events')
        if cached is not None:
            return cached
        try:
            events_ref = self.ref.child('events')
            data = events_ref.get() or {}
            self._set_cache('events', data, ttl=30)
            return data
        except Exception as e:
            print(f"Error getting all events: {e}")
            return {}

    def get_events_by_organizer(self, organizer_id):
        """Get events created by a specific organizer"""
        try:
            all_events = self.get_all_events() or {}
            organizer_events = {}
            for event_id, event_data in all_events.items():
                if event_data and event_data.get('organizer_id') == organizer_id:
                    organizer_events[event_id] = event_data
            return organizer_events
        except Exception as e:
            print(f"Error getting events by organizer: {e}")
            return {}

    def save_event_attendee(self, attendee_id, attendee_data):
        """Save event attendee data to Firebase"""
        try:
            attendees_ref = self.ref.child('event_attendees')
            attendees_ref.child(attendee_id).set(attendee_data)
            self.invalidate_cache('event_attendees', f'attendee_{attendee_id}')
            return True
        except Exception as e:
            print(f"Error saving event attendee: {e}")
            return False

    def get_all_event_attendees(self):
        """Get all event attendees with caching"""
        cached = self._get_cache('event_attendees')
        if cached is not None:
            return cached
        try:
            attendees_ref = self.ref.child('event_attendees')
            data = attendees_ref.get() or {}
            self._set_cache('event_attendees', data, ttl=30)
            return data
        except Exception as e:
            print(f"Error getting all event attendees: {e}")
            return {}

    def get_event_attendee(self, attendee_id):
        """Get event attendee data from Firebase"""
        cached = self._get_cache(f'attendee_{attendee_id}')
        if cached is not None:
            return cached
        try:
            all_attendees = self.get_all_event_attendees()
            if attendee_id in all_attendees:
                return all_attendees[attendee_id]
            attendee_ref = self.ref.child('event_attendees').child(attendee_id)
            data = attendee_ref.get()
            if data is not None:
                self._set_cache(f'attendee_{attendee_id}', data, ttl=30)
            return data
        except Exception as e:
            print(f"Error getting event attendee: {e}")
            return None

    def get_event_attendees_by_event(self, event_id):
        """Get all attendees for a specific event using cached attendees"""
        try:
            all_attendees = self.get_all_event_attendees() or {}
            event_attendees = {}
            for attendee_id, attendee_data in all_attendees.items():
                if attendee_data and isinstance(attendee_data, dict):
                    if event_id in attendee_data.get('registered_events', []):
                        event_attendees[attendee_id] = attendee_data
            return event_attendees
        except Exception as e:
            print(f"Error getting event attendees: {e}")
            return {}

    def register_attendee_for_event(self, attendee_id, event_id, registration_data):
        """Register an attendee for an event"""
        try:
            # Get or create attendee data
            attendee_data = self.get_event_attendee(attendee_id)
            if not attendee_data:
                attendee_data = {
                    'attendee_name': registration_data.get('name', ''),
                    'whatsapp_number': registration_data.get('whatsapp_number', ''),
                    'email': registration_data.get('email', ''),
                    'enrollment_no': registration_data.get('enrollment_no', ''),
                    'school': registration_data.get('school', ''),
                    'branch': registration_data.get('branch', ''),
                    'semester': registration_data.get('semester', ''),
                    'registered_events': []
                }
            
            # Add event to attendee's registered events if not already registered
            if event_id not in attendee_data.get('registered_events', []):
                attendee_data.setdefault('registered_events', []).append(event_id)
                self.save_event_attendee(attendee_id, attendee_data)
            
            # Also save the registration record
            registration_ref = self.ref.child('event_registrations').child(event_id).child(attendee_id)
            registration_ref.set({
                'registration_date': registration_data.get('registration_date'),
                'status': 'registered',
                'attendee_name': registration_data.get('name', ''),
                'whatsapp_number': registration_data.get('whatsapp_number', ''),
                'email': registration_data.get('email', ''),
                'enrollment_no': registration_data.get('enrollment_no', ''),
                'school': registration_data.get('school', ''),
                'branch': registration_data.get('branch', ''),
                'semester': registration_data.get('semester', '')
            })
            
            return True
        except Exception as e:
            print(f"Error registering attendee for event: {e}")
            return False

    def save_event_attendance(self, event_id, session_date, attendee_id, attendee_name, status="P", device_data=None, location_data=None):
        """Save event attendance record to Firebase with geofencing and device tracking"""
        try:
            attendance_ref = self.ref.child('event_attendance')
            record_key = f"{event_id}_{session_date}"
            
            # Get registration data to include in attendance record
            registration_data = self.get_event_registration_by_enrollment(event_id, attendee_id) if attendee_id else None
            if not registration_data:
                # Try with attendee_id as direct lookup
                reg_ref = self.ref.child("event_registrations").child(event_id).child(attendee_id)
                registration_data = reg_ref.get()
            
            # Prepare attendance record with comprehensive data
            attendance_record = {
                'attendee_name': attendee_name,
                'status': status,
                'timestamp': session_date,
                'marked_at': datetime.now().isoformat()
            }
            
            # Include registration details if available
            if registration_data:
                attendance_record.update({
                    'enrollment_no': registration_data.get('enrollment_no', ''),
                    'name': registration_data.get('name', attendee_name),
                    'school': registration_data.get('school', ''),
                    'branch': registration_data.get('branch', ''),
                    'semester': registration_data.get('semester', ''),
                    'email': registration_data.get('email', ''),
                    'whatsapp_number': registration_data.get('whatsapp_number', ''),
                    'attendee_phone': registration_data.get('whatsapp_number', '')
                })
            
            # Add device information if provided
            if device_data:
                attendance_record['device_info'] = {
                    'device_id': device_data.get('deviceId'),
                    'device_fingerprint': device_data.get('fingerprint'),
                    'user_agent': device_data.get('userAgent', '')
                }
            
            # Add location information if provided
            if location_data:
                attendance_record['location_info'] = {
                    'latitude': location_data.get('lat'),
                    'longitude': location_data.get('lng'),
                    'accuracy': location_data.get('accuracy'),
                    'timestamp': location_data.get('timestamp')
                }
            
            attendance_ref.child(record_key).child(attendee_id).set(attendance_record)
            self.invalidate_cache(f'attendance_{event_id}')
            return True
        except Exception as e:
            print(f"Error saving event attendance: {e}")
            return False

    def get_event_attendance_data(self, event_id):
        """Get attendance records for a specific event with caching"""
        cache_key = f'attendance_{event_id}'
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        try:
            attendance_ref = self.ref.child('event_attendance')
            records = attendance_ref.get()
            
            if not records:
                self._set_cache(cache_key, {}, ttl=15)
                return {}
            
            # Filter records for specific event
            filtered_records = {}
            search_key = f"{event_id}_"
            
            for key, value in records.items():
                if key.startswith(search_key):
                    filtered_records[key] = value
            
            self._set_cache(cache_key, filtered_records, ttl=15)
            return filtered_records
        except Exception as e:
            print(f"Error getting event attendance records: {e}")
            return {}

    def update_current_event(self, event_info):
        """Save current active event information to Firebase"""
        try:
            current_event_ref = self.ref.child('current_event')
            current_event_ref.set(event_info)
            self.invalidate_cache('current_event')
            return True
        except Exception as e:
            print(f"Error updating current event: {e}")
            return False

    def get_current_event(self):
        """Get current active event information from Firebase with caching"""
        cached = self._get_cache('current_event')
        if cached is not None:
            return cached
        try:
            current_event_ref = self.ref.child('current_event')
            data = current_event_ref.get()
            if data is not None:
                self._set_cache('current_event', data, ttl=30)
            return data
        except Exception as e:
            print(f"Error getting current event: {e}")
            return None

    def get_attendee_by_phone(self, phone_number):
        """Get event attendee by WhatsApp phone number using cached attendees"""
        try:
            attendees = self.get_all_event_attendees()
            if not attendees:
                return None
            
            for attendee_id, attendee_data in attendees.items():
                if attendee_data and isinstance(attendee_data, dict):
                    if attendee_data.get('whatsapp_number') == phone_number:
                        return {
                            'attendee_id': attendee_id,
                            **attendee_data
                        }
            return None
        except Exception as e:
            print(f"Error getting attendee by phone: {e}")
            return None

    def check_device_attendance(self, event_id, session_date, device_signature):
        """Check if device has already been used for attendance today"""
        try:
            device_log_ref = self.ref.child('device_usage').child(f"{event_id}_{session_date}")
            existing_devices = device_log_ref.get() or {}
            
            device_id = device_signature.get('deviceId')
            fingerprint = device_signature.get('fingerprint')
            
            # Check by device ID
            if device_id and device_id in existing_devices:
                return False, f"Device {device_id} has already been used for attendance today"
            
            # Removed strict fingerprint check to prevent false positives on identical device models
            # We rely on the unique deviceId stored in localStorage which is sufficient for 
            # this use case while preventing accidental reuse.
            
            return True, "Device is valid for attendance"
        except Exception as e:
            print(f"Error checking device attendance: {e}")
            return True, "Device check failed, allowing attendance"

    def save_device_usage(self, event_id, session_date, device_signature, attendee_id, ip_address=None):
        """Log device usage to prevent reuse"""
        try:
            device_log_ref = self.ref.child('device_usage').child(f"{event_id}_{session_date}")
            device_id = device_signature.get('deviceId')
            
            device_log_ref.child(device_id).set({
                'fingerprint': device_signature.get('fingerprint'),
                'attendee_id': attendee_id,
                'marked_at': datetime.now().isoformat(),
                'ip_address': ip_address,
                'user_agent': device_signature.get('userAgent', ''),
                'browser_validated': 'generic',
                'device_details': {
                    'timestamp': device_signature.get('timestamp'),
                    'verified_browser': True
                }
            })
            return True
        except Exception as e:
            print(f"Error saving device usage: {e}")
            return False

    def validate_geofence(self, user_lat, user_lng, event_lat, event_lng, radius_meters):
        """Validate if user is within geofence radius"""
        try:
            import math
            
            # Convert to radians
            lat1 = math.radians(user_lat)
            lon1 = math.radians(user_lng)
            lat2 = math.radians(event_lat)
            lon2 = math.radians(event_lng)
            
            # Haversine formula
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            
            # Distance in meters
            distance = 6371000 * c  # Earth's radius in meters
            
            return distance <= radius_meters, distance
        except Exception as e:
            print(f"Error validating geofence: {e}")
            return False, float('inf')

    def get_attendee_by_id(self, attendee_id):
        """Get attendee by ID for direct attendance marking"""
        try:
            attendee_ref = self.ref.child('event_attendees').child(attendee_id)
            attendee_data = attendee_ref.get()
            
            if attendee_data:
                return {
                    'attendee_id': attendee_id,
                    **attendee_data
                }
            return None
        except Exception as e:
            print(f"Error getting attendee by ID: {e}")
            return None

    def save_geofenced_attendance(self, event_id, attendee_data, device_signature, location_data, ip_address=None):
        """Save attendance with full geofencing and device validation"""
        try:
            session_date = datetime.now().strftime("%Y-%m-%d")
            attendee_id = attendee_data['attendee_id']
            attendee_name = attendee_data.get('attendee_name', attendee_data.get('name', 'Unknown'))
            
            # Check if attendance already marked
            existing_attendance = self.get_event_attendance_data(event_id)
            record_key = f"{event_id}_{session_date}"
            
            if record_key in existing_attendance and attendee_id in existing_attendance[record_key]:
                return False, "Attendance already marked for today"
            
            # Check device usage
            device_valid, device_message = self.check_device_attendance(event_id, session_date, device_signature)
            if not device_valid:
                return False, device_message
            
            # Save attendance record with all details including missed classes
            success = self.save_event_attendance_with_missed_classes(
                event_id, 
                session_date, 
                attendee_data.get('enrollment_no', attendee_id),  # Use enrollment_no as the key
                attendee_name, 
                "P", 
                device_signature, 
                location_data,
                attendee_data  # Pass complete attendee data including missed classes
            )
            
            if success:
                # Update the attendee record in event_attendees with missed classes and status
                # This ensures the "Missed Classes" report can find the data by querying attendees
                try:
                    attendee_update = {
                        'attendance_marked': True,
                        'last_attendance': datetime.now().isoformat()
                    }
                    
                    # Add missed classes if present
                    if 'missed_classes' in attendee_data:
                        attendee_update['missed_classes'] = attendee_data['missed_classes']
                        print(f"DEBUG: Updating attendee {attendee_id} with missed classes")
                    
                    self.ref.child('event_attendees').child(attendee_id).update(attendee_update)
                except Exception as update_error:
                    print(f"Error updating attendee record: {update_error}")

                # Log device usage
                self.save_device_usage(event_id, session_date, device_signature, attendee_id, ip_address)
                return True, "Attendance marked successfully"
            else:
                return False, "Failed to save attendance record"
                
        except Exception as e:
            print(f"Error saving geofenced attendance: {e}")
            return False, f"Error: {str(e)}"

    def save_event_attendance_with_missed_classes(self, event_id, session_date, attendee_id, attendee_name, status="P", device_data=None, location_data=None, complete_attendee_data=None):
        """Save event attendance record with missed classes data"""
        try:
            attendance_ref = self.ref.child('event_attendance')
            record_key = f"{event_id}_{session_date}"
            
            # Get registration data to include in attendance record
            registration_data = self.get_event_registration_by_enrollment(event_id, attendee_id) if attendee_id else None
            if not registration_data:
                # Try with attendee_id as direct lookup
                reg_ref = self.ref.child("event_registrations").child(event_id).child(attendee_id)
                registration_data = reg_ref.get()
            
            # Prepare attendance record with comprehensive data
            attendance_record = {
                'attendee_name': attendee_name,
                'status': status,
                'timestamp': session_date,
                'marked_at': datetime.now().isoformat()
            }
            
            # Include registration details if available
            if registration_data:
                attendance_record.update({
                    'enrollment_no': registration_data.get('enrollment_no', ''),
                    'name': registration_data.get('name', attendee_name),
                    'school': registration_data.get('school', ''),
                    'branch': registration_data.get('branch', ''),
                    'semester': registration_data.get('semester', ''),
                    'email': registration_data.get('email', ''),
                    'whatsapp_number': registration_data.get('whatsapp_number', ''),
                })
            
            # Include missed classes data if provided
            if complete_attendee_data and 'missed_classes' in complete_attendee_data:
                missed_classes = complete_attendee_data['missed_classes']
                print(f"DEBUG: Firebase save - missed_classes data: {missed_classes}")
                print(f"DEBUG: Firebase save - missed_classes type: {type(missed_classes)}")
                if missed_classes:  # Only add if not empty
                    attendance_record['missed_classes'] = missed_classes
                    print(f"DEBUG: Firebase save - Added missed_classes to attendance_record")
                else:
                    print(f"DEBUG: Firebase save - missed_classes is empty, not adding to record")
            else:
                print(f"DEBUG: Firebase save - No missed_classes in complete_attendee_data")
                print(f"DEBUG: Firebase save - complete_attendee_data keys: {list(complete_attendee_data.keys()) if complete_attendee_data else 'None'}")
            
            # Add device and location information
            if device_data:
                attendance_record['device_info'] = {
                    'device_id': device_data,
                    'device_signature': device_data,
                    'marked_at': datetime.now().isoformat()
                }
            
            if location_data:
                attendance_record['location_info'] = {
                    'latitude': location_data.get('lat'),
                    'longitude': location_data.get('lng'),
                    'accuracy': location_data.get('accuracy'),
                    'timestamp': location_data.get('timestamp')
                }
            
            # Save the attendance record
            attendance_ref.child(record_key).child(attendee_id).set(attendance_record)
            return True
            
        except Exception as e:
            print(f"Error saving attendance with missed classes: {e}")
            return False
    
    def get_teacher(self, teacher_id):
        """Get teacher data from Firebase"""
        try:
            teacher_ref = self.ref.child('teachers').child(teacher_id)
            return teacher_ref.get()
        except Exception as e:
            print(f"Error getting teacher: {e}")
            return None
    
    def get_all_teachers(self):
        """Get all teachers from Firebase"""
        try:
            teachers_ref = self.ref.child('teachers')
            return teachers_ref.get() or {}
        except Exception as e:
            print(f"Error getting all teachers: {e}")
            return {}
    
    def save_attendance_record(self, subject_code, class_section, date, student_id, student_name, status="P"):
        """Save attendance record to Firebase"""
        try:
            attendance_ref = self.ref.child('attendance')
            record_key = f"{subject_code}_{class_section}_{date}"
            
            attendance_ref.child(record_key).child(student_id).set({
                'student_name': student_name,
                'status': status,
                'timestamp': date
            })
            return True
        except Exception as e:
            print(f"Error saving attendance: {e}")
            return False
    
    def add_attendance_record(self, subject_code, section, teacher_id, student_id, date, status):
        """Add or update attendance record for a specific student and date"""
        try:
            attendance_ref = self.ref.child('attendance')
            record_key = f"{subject_code}_{section}_{date}"
            
            # Get student name from students collection
            student_ref = self.ref.child('students').child(student_id)
            student_data = student_ref.get()
            student_name = student_data.get('student_name', 'Unknown') if student_data else 'Unknown'
            
            # Update or create the attendance record
            attendance_ref.child(record_key).child(student_id).set({
                'student_name': student_name,
                'status': status,
                'timestamp': date,
                'manual_override': True
            })
            
            return True
            
        except Exception as e:
            print(f"Error adding attendance record: {e}")
            return False

    def update_attendance_status(self, subject_code, section, student_id, date, status):
        """Update attendance status for a specific record"""
        try:
            attendance_ref = self.ref.child('attendance')
            record_key = f"{subject_code}_{section}_{date}"
            
            # Check if record exists
            record_ref = attendance_ref.child(record_key).child(student_id)
            existing_record = record_ref.get()
            
            if existing_record:
                # Update existing record
                record_ref.update({
                    'status': status,
                    'timestamp': date
                })
                return True
            else:
                # No existing record found
                return False
                
        except Exception as e:
            print(f"Error updating attendance status: {e}")
            return False

    def get_attendance_data(self, subject_code, section):
        """Get attendance records for a specific subject and class"""
        try:
            attendance_ref = self.ref.child('attendance')
            records = attendance_ref.get()
            
            if not records:
                return {}
            
            # Filter records for specific subject and class
            filtered_records = {}
            search_key = f"{subject_code}_{section}"
            
            for key, value in records.items():
                if key.startswith(search_key):
                    filtered_records[key] = value
            
            return filtered_records
        except Exception as e:
            print(f"Error getting attendance records: {e}")
            return {}
    
    def save_student_info(self, enrollment_no, student_data):
        """Save student information to Firebase"""
        try:
            students_ref = self.ref.child('students')
            students_ref.child(enrollment_no).set(student_data)
            return True
        except Exception as e:
            print(f"Error saving student info: {e}")
            return False
    
    def get_student_by_enrollment(self, enrollment_no):
        """Get student data by enrollment number"""
        try:
            student_ref = self.ref.child('students').child(enrollment_no)
            return student_ref.get()
        except Exception as e:
            print(f"Error getting student by enrollment: {e}")
            return None
    
    def get_all_students(self):
        """Get all students from Firebase with caching"""
        cached = self._get_cache('students')
        if cached is not None:
            return cached
        try:
            students_ref = self.ref.child('students')
            data = students_ref.get() or {}
            self._set_cache('students', data, ttl=60)
            return data
        except Exception as e:
            print(f"Error getting all students: {e}")
            return {}
    
    def update_student_info(self, enrollment_no, student_data):
        """Update existing student information"""
        try:
            student_ref = self.ref.child('students').child(enrollment_no)
            student_ref.update(student_data)
            self.invalidate_cache('students')
            return True
        except Exception as e:
            print(f"Error updating student info: {e}")
            return False
    
    def delete_student(self, enrollment_no):
        """Delete student from Firebase"""
        try:
            student_ref = self.ref.child('students').child(enrollment_no)
            student_ref.delete()
            self.invalidate_cache('students')
            return True
        except Exception as e:
            print(f"Error deleting student: {e}")
            return False

    
    def search_students_by_name(self, search_name):
        """Search students by name (partial match)"""
        try:
            students = self.get_all_students()
            matching_students = {}
            
            search_name = search_name.lower()
            for enrollment_no, student_data in students.items():
                student_name = student_data.get('student_name', '').lower()
                if search_name in student_name:
                    matching_students[enrollment_no] = student_data
            
            return matching_students
        except Exception as e:
            print(f"Error searching students: {e}")
            return {}
    
    def get_students_by_school_branch(self, school=None, branch=None):
        """Get students filtered by school and/or branch"""
        try:
            students = self.get_all_students()
            filtered_students = {}
            
            for enrollment_no, student_data in students.items():
                matches = True
                
                if school and student_data.get('school', '').lower() != school.lower():
                    matches = False
                
                if branch and student_data.get('branch', '').lower() != branch.lower():
                    matches = False
                
                if matches:
                    filtered_students[enrollment_no] = student_data
            
            return filtered_students
        except Exception as e:
            print(f"Error filtering students: {e}")
            return {}
    
    def get_student_by_phone(self, phone_number):
        """Get student by WhatsApp phone number"""
        try:
            students_ref = self.ref.child('students')
            students = students_ref.get()
            
            if not students:
                return None
            
            for enrollment_no, student_data in students.items():
                if student_data.get('whatsapp_number') == phone_number:
                    return {
                        'enrollment_no': enrollment_no,
                        **student_data
                    }
            return None
        except Exception as e:
            print(f"Error getting student by phone: {e}")
            return None
    
    def update_current_class(self, class_info):
        """Save current class information to Firebase"""
        try:
            current_class_ref = self.ref.child('current_class')
            current_class_ref.set(class_info)
            return True
        except Exception as e:
            print(f"Error updating current class: {e}")
            return False
    
    def get_current_class(self):
        """Get current class information from Firebase"""
        try:
            current_class_ref = self.ref.child('current_class')
            return current_class_ref.get()
        except Exception as e:
            print(f"Error getting current class: {e}")
            return None

    def save_admin_data(self, admin_data):
        """Save admin configuration data to Firebase"""
        try:
            admin_ref = self.ref.child('admin')
            admin_ref.set(admin_data)
            return True
        except Exception as e:
            print(f"Error saving admin data: {e}")
            return False

    def get_admin_data(self):
        """Get admin configuration data from Firebase"""
        try:
            admin_ref = self.ref.child('admin')
            return admin_ref.get()
        except Exception as e:
            print(f"Error getting admin data: {e}")
            return None

    def save_subject(self, subject_code, subject_data):
        """Save subject data to Firebase"""
        try:
            subjects_ref = self.ref.child('subjects')
            subjects_ref.child(subject_code).set(subject_data)
            return True
        except Exception as e:
            print(f"Error saving subject: {e}")
            return False

    def get_all_subjects(self):
        """Get all subjects from Firebase"""
        try:
            subjects_ref = self.ref.child('subjects')
            return subjects_ref.get() or {}
        except Exception as e:
            print(f"Error getting all subjects: {e}")
            return {}

    def delete_subject(self, subject_code):
        """Delete subject from Firebase"""
        try:
            subjects_ref = self.ref.child('subjects')
            subjects_ref.child(subject_code).delete()
            return True
        except Exception as e:
            print(f"Error deleting subject: {e}")
            return False

    def save_schedule_data(self, teacher_id, schedule_data):
        """Save teacher schedule data to Firebase"""
        try:
            schedule_ref = self.ref.child('schedules')
            schedule_ref.child(teacher_id).set(schedule_data)
            return True
        except Exception as e:
            print(f"Error saving schedule: {e}")
            return False

    def get_schedule_data(self, teacher_id):
        """Get teacher schedule data from Firebase"""
        try:
            schedule_ref = self.ref.child('schedules').child(teacher_id)
            return schedule_ref.get()
        except Exception as e:
            print(f"Error getting schedule: {e}")
            return None

    def save_qr_session(self, session_data):
        """Save QR code session data to Firebase"""
        try:
            qr_ref = self.ref.child('qr_sessions')
            timestamp = session_data.get('timestamp', 'unknown')
            qr_ref.child(timestamp).set(session_data)
            return True
        except Exception as e:
            print(f"Error saving QR session: {e}")
            return False

    def get_attendance_analytics(self, subject_code=None, date_range=None):
        """Get attendance analytics data"""
        try:
            attendance_ref = self.ref.child('attendance')
            all_records = attendance_ref.get() or {}
            
            # Ensure all_records is a dictionary, not a list
            if not isinstance(all_records, dict):
                print(f"Warning: Attendance records is not a dict, it's {type(all_records)}")
                all_records = {}
            
            analytics = {
                'total_sessions': 0,
                'total_students': set(),
                'attendance_by_date': {},
                'student_attendance_rate': {}
            }
            
            for record_key, students_data in all_records.items():
                # Filter by subject if specified
                if subject_code and not record_key.startswith(subject_code):
                    continue
                
                # Ensure students_data is a dictionary
                if not isinstance(students_data, dict):
                    print(f"Warning: Students data for {record_key} is not a dict, it's {type(students_data)}")
                    continue
                
                analytics['total_sessions'] += 1
                date = record_key.split('_')[-1]
                analytics['attendance_by_date'][date] = len(students_data)
                
                for student_id, student_info in students_data.items():
                    # Ensure student_info is a dictionary
                    if not isinstance(student_info, dict):
                        print(f"Warning: Student info for {student_id} is not a dict, it's {type(student_info)}")
                        continue
                        
                    analytics['total_students'].add(student_id)
                    
                    if student_id not in analytics['student_attendance_rate']:
                        analytics['student_attendance_rate'][student_id] = {
                            'present': 0,
                            'total': 0,
                            'name': student_info.get('student_name', 'Unknown')
                        }
                    
                    analytics['student_attendance_rate'][student_id]['total'] += 1
                    if student_info.get('status') == 'P':
                        analytics['student_attendance_rate'][student_id]['present'] += 1
            
            # Convert set to count
            analytics['total_students'] = len(analytics['total_students'])
            
            return analytics
        except Exception as e:
            print(f"Error getting attendance analytics: {e}")
            return {}

    def backup_all_data(self):
        """Create a backup of all data in Firebase"""
        try:
            root_ref = self.ref
            all_data = root_ref.get()
            
            # Save backup with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_ref = self.ref.child('backups').child(timestamp)
            backup_ref.set(all_data)
            
            return True
        except Exception as e:
            print(f"Error creating backup: {e}")
            return False

    def save_session_info(self, session_data):
        """Save class session information to Firebase"""
        try:
            sessions_ref = self.ref.child('active_sessions')
            session_key = f"{session_data['teacher_username']}_{session_data['subject_code']}_{session_data['class_section']}"
            sessions_ref.child(session_key).set(session_data)
            return True
        except Exception as e:
            print(f"Error saving session info: {e}")
            return False

    def update_session_status(self, session_update):
        """Update session status in Firebase"""
        try:
            sessions_ref = self.ref.child('active_sessions')
            session_key = f"{session_update['teacher_username']}_{session_update['subject_code']}_{session_update['class_section']}"
            
            # Get existing session data
            existing_session = sessions_ref.child(session_key).get()
            if existing_session:
                existing_session.update(session_update)
                sessions_ref.child(session_key).set(existing_session)
            
            return True
        except Exception as e:
            print(f"Error updating session status: {e}")
            return False

    def get_active_sessions(self, teacher_username=None):
        """Get active sessions from Firebase"""
        try:
            sessions_ref = self.ref.child('active_sessions')
            all_sessions = sessions_ref.get() or {}
            
            if teacher_username:
                # Filter by teacher
                teacher_sessions = {}
                for session_key, session_data in all_sessions.items():
                    if session_data.get('teacher_username') == teacher_username:
                        teacher_sessions[session_key] = session_data
                return teacher_sessions
            
            return all_sessions
        except Exception as e:
            print(f"Error getting active sessions: {e}")
            return {}

    def end_all_sessions_for_teacher(self, teacher_username):
        """End all active sessions for a specific teacher"""
        try:
            sessions_ref = self.ref.child('active_sessions')
            all_sessions = sessions_ref.get() or {}
            
            from datetime import datetime
            current_time = datetime.now().isoformat()
            
            for session_key, session_data in all_sessions.items():
                if session_data.get('teacher_username') == teacher_username and session_data.get('status') == 'active':
                    session_data.update({
                        'status': 'ended',
                        'session_end_time': current_time,
                        'end_reason': 'teacher_logout'
                    })
                    sessions_ref.child(session_key).set(session_data)
            
            return True
        except Exception as e:
            print(f"Error ending teacher sessions: {e}")
            return False
    
    def delete_session(self, session_key):
        """Delete a session from Firebase"""
        try:
            sessions_ref = self.ref.child('active_sessions')
            sessions_ref.child(session_key).delete()
            return True
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False
    
    def delete_sessions_for_teacher(self, teacher_username):
        """Delete all sessions for a specific teacher"""
        try:
            sessions_ref = self.ref.child('active_sessions')
            all_sessions = sessions_ref.get() or {}
            
            for session_key, session_data in all_sessions.items():
                if session_data.get('teacher_username') == teacher_username:
                    sessions_ref.child(session_key).delete()
            
            return True
        except Exception as e:
            print(f"Error deleting teacher sessions: {e}")
            return False
    
    def save_class_sheets(self, class_sheets_data):
        """Save class sheet mappings to Firebase"""
        try:
            class_sheets_ref = self.ref.child('class_sheets')
            class_sheets_ref.set(class_sheets_data)
            return True
        except Exception as e:
            print(f"Error saving class sheets: {e}")
            return False
    
    def get_class_sheets(self):
        """Get class sheet mappings from Firebase"""
        try:
            class_sheets_ref = self.ref.child('class_sheets')
            return class_sheets_ref.get() or {}
        except Exception as e:
            print(f"Error getting class sheets: {e}")
            return {}
    
    def save_class_sheet(self, class_key, sheet_data):
        """Save a single class sheet mapping to Firebase"""
        try:
            class_sheet_ref = self.ref.child('class_sheets').child(class_key)
            class_sheet_ref.set(sheet_data)
            return True
        except Exception as e:
            print(f"Error saving class sheet: {e}")
            return False
    
    def save_class_students(self, class_key, students_data):
        """Save student data for a specific class to Firebase"""
        try:
            students_ref = self.ref.child('class_students').child(class_key)
            
            # Convert list to dict for Firebase storage
            students_dict = {}
            for student in students_data:
                enrollment_no = student.get('enrollment_no')
                if enrollment_no:
                    students_dict[enrollment_no] = student
            
            students_ref.set(students_dict)
            return True
        except Exception as e:
            print(f"Error saving class students: {e}")
            return False
    
    def get_class_students(self, class_key):
        """Get student data for a specific class from Firebase"""
        try:
            students_ref = self.ref.child('class_students').child(class_key)
            students_dict = students_ref.get() or {}
            
            # Convert dict back to list
            students_list = []
            for enrollment_no, student_data in students_dict.items():
                students_list.append(student_data)
            
            return students_list
        except Exception as e:
            print(f"Error getting class students: {e}")
            return []
    
    def get_active_qr_codes(self):
        """Get active QR codes from Firebase"""
        try:
            qr_ref = self.ref.child('active_qr_codes')
            return qr_ref.get() or {}
        except Exception as e:
            print(f"Error getting active QR codes: {e}")
            return {}

    def save_active_qr_code(self, secret_key, qr_data):
        """Save active QR code to Firebase"""
        try:
            qr_ref = self.ref.child('active_qr_codes')
            qr_ref.child(secret_key).set(qr_data)
            return True
        except Exception as e:
            print(f"Error saving active QR code: {e}")
            return False

    def remove_active_qr_code(self, secret_key):
        """Remove active QR code from Firebase"""
        try:
            qr_ref = self.ref.child('active_qr_codes')
            qr_ref.child(secret_key).delete()
            return True
        except Exception as e:
            print(f"Error removing active QR code: {e}")
            return False

    def get_pending_user_info(self):
        """Get pending user info from Firebase"""
        try:
            pending_ref = self.ref.child('pending_user_info')
            return pending_ref.get() or {}
        except Exception as e:
            print(f"Error getting pending user info: {e}")
            return {}

    def save_pending_user_info(self, phone_number, user_data):
        """Save pending user info to Firebase"""
        try:
            pending_ref = self.ref.child('pending_user_info')
            pending_ref.child(phone_number).set(user_data)
            return True
        except Exception as e:
            print(f"Error saving pending user info: {e}")
            return False

    def remove_pending_user_info(self, phone_number):
        """Remove pending user info from Firebase"""
        try:
            pending_ref = self.ref.child('pending_user_info')
            pending_ref.child(phone_number).delete()
            return True
        except Exception as e:
            print(f"Error removing pending user info: {e}")
            return False

    def delete_event(self, event_id):
        """Delete event and all associated data"""
        try:
            # Delete the event itself
            event_ref = self.ref.child('events').child(event_id)
            event_ref.delete()
            
            # Delete attendees for this event
            attendees_ref = self.ref.child('event_attendees')
            all_attendees = attendees_ref.get() or {}
            
            for attendee_id, attendee_data in all_attendees.items():
                if isinstance(attendee_data, dict):
                    # Check if this attendee is registered for the event being deleted
                    attendee_events = attendee_data.get('events', {})
                    if event_id in attendee_events:
                        # Remove this event from the attendee's events
                        attendees_ref.child(attendee_id).child('events').child(event_id).delete()
                        
                        # If this was the attendee's only event, delete the entire attendee record
                        remaining_events = attendee_events.copy()
                        remaining_events.pop(event_id, None)
                        if not remaining_events:
                            attendees_ref.child(attendee_id).delete()
            
            # Delete attendance records
            attendance_ref = self.ref.child('event_attendance')
            all_attendance = attendance_ref.get() or {}
            
            for record_key in list(all_attendance.keys()):
                if record_key.startswith(f"{event_id}_"):
                    attendance_ref.child(record_key).delete()
            
            # Delete device usage records
            device_usage_ref = self.ref.child('device_usage')
            all_device_usage = device_usage_ref.get() or {}
            
            for record_key in list(all_device_usage.keys()):
                if record_key.startswith(f"{event_id}_"):
                    device_usage_ref.child(record_key).delete()
            
            # Clear current event if it matches the deleted event
            current_event = self.get_current_event()
            if current_event and current_event.get('event_id') == event_id:
                self.ref.child('current_event').delete()
            
            print(f"Successfully deleted event {event_id} and all associated data")
            return True
            
        except Exception as e:
            print(f"Error deleting event {event_id}: {e}")
            return False

    def get_event_time_slots(self, event_id):
        """Get time slots for an event"""
        try:
            slots_ref = self.ref.child('event_time_slots').child(event_id)
            slots = slots_ref.get()
            return slots or []
        except Exception as e:
            print(f"Error getting time slots for event {event_id}: {e}")
            return []

    def save_event_time_slots(self, event_id, slots):
        """Save time slots for an event"""
        try:
            slots_ref = self.ref.child('event_time_slots').child(event_id)
            slots_ref.set(slots)
            return True
        except Exception as e:
            print(f"Error saving time slots for event {event_id}: {e}")
            return False

    def get_event_registration_by_enrollment(self, event_id, enrollment_no):
        """Get event registration data by enrollment number for a specific event"""
        try:
            # Search in event registrations
            registrations_ref = self.ref.child('event_registrations').child(event_id)
            all_registrations = registrations_ref.get() or {}
            
            enrollment_no = enrollment_no.strip().upper()
            
            # Search through all registrations for this event
            for attendee_id, registration_data in all_registrations.items():
                if registration_data and registration_data.get('enrollment_no', '').strip().upper() == enrollment_no:
                    return {
                        'attendee_id': attendee_id,
                        'name': registration_data.get('attendee_name', ''),
                        'email': registration_data.get('email', ''),
                        'whatsapp_number': registration_data.get('whatsapp_number', ''),
                        'enrollment_no': registration_data.get('enrollment_no', ''),
                        'school': registration_data.get('school', ''),
                        'branch': registration_data.get('branch', ''),
                        'semester': registration_data.get('semester', ''),
                        'registration_date': registration_data.get('registration_date', '')
                    }
            return None
            
        except Exception as e:
            print(f"Error getting event registration by enrollment: {e}")
            return None

# Create a global instance
firebase_db = FirebaseDB()

# Helper functions for backward compatibility with existing app.py code
def get_teacher(teacher_username):
    """Get teacher data"""
    return firebase_db.get_teacher(teacher_username)

def save_teacher(teacher_username, teacher_data):
    """Save teacher data"""
    return firebase_db.save_teacher(teacher_username, teacher_data)

def get_all_teachers():
    """Get all teachers"""
    return firebase_db.get_all_teachers()

def get_current_class():
    """Get current class info"""
    return firebase_db.get_current_class()

def update_current_class(class_info):
    """Update current class info"""
    return firebase_db.update_current_class(class_info)

def get_active_qr_codes():
    """Get active QR codes"""
    return firebase_db.get_active_qr_codes()

def save_active_qr_code(secret_key, qr_data):
    """Save active QR code"""
    return firebase_db.save_active_qr_code(secret_key, qr_data)

def remove_active_qr_code(secret_key):
    """Remove active QR code"""
    return firebase_db.remove_active_qr_code(secret_key)

def get_pending_user_info():
    """Get pending user info"""
    return firebase_db.get_pending_user_info()

def save_pending_user_info(phone_number, user_data):
    """Save pending user info"""
    return firebase_db.save_pending_user_info(phone_number, user_data)

def remove_pending_user_info(phone_number):
    """Remove pending user info"""
    return firebase_db.remove_pending_user_info(phone_number)

def get_class_sheets():
    """Get class sheets"""
    return firebase_db.get_class_sheets()

def save_class_sheet(class_key, sheet_data):
    """Save class sheet"""
    return firebase_db.save_class_sheet(class_key, sheet_data)

def delete_class_sheet(class_key):
    """Delete class sheet"""
    try:
        firebase_db.ref.child('class_sheets').child(class_key).delete()
        return True
    except Exception as e:
        print(f"Error deleting class sheet {class_key}: {e}")
        return False

def get_admin_credentials():
    """Get admin credentials"""
    try:
        data = firebase_db.ref.child('admin_credentials').get()
        return data if data else {}
    except Exception as e:
        print(f"Error retrieving admin credentials: {e}")
        return {}

def save_admin_credentials(credentials):
    """Save admin credentials"""
    try:
        firebase_db.ref.child('admin_credentials').set(credentials)
        return True
    except Exception as e:
        print(f"Error saving admin credentials: {e}")
        return False

def update_teacher(username, teacher_data):
    """Update teacher data"""
    try:
        firebase_db.ref.child('teachers').child(username).update(teacher_data)
        return True
    except Exception as e:
        print(f"Error updating teacher {username}: {e}")
        return False

# Helper functions for event management
def save_event_organizer(organizer_id, organizer_data):
    """Save event organizer data"""
    return firebase_db.save_event_organizer(organizer_id, organizer_data)

def get_event_organizer(organizer_id):
    """Get event organizer data"""
    return firebase_db.get_event_organizer(organizer_id)

def get_all_event_organizers():
    """Get all event organizers"""
    return firebase_db.get_all_event_organizers()

def save_event(event_id, event_data):
    """Save event data"""
    return firebase_db.save_event(event_id, event_data)

def get_event(event_id):
    """Get event data"""
    return firebase_db.get_event(event_id)

def get_all_events():
    """Get all events"""
    return firebase_db.get_all_events()

def get_events_by_organizer(organizer_id):
    """Get events by organizer"""
    return firebase_db.get_events_by_organizer(organizer_id)

def save_event_attendee(attendee_id, attendee_data):
    """Save event attendee data"""
    return firebase_db.save_event_attendee(attendee_id, attendee_data)

def get_event_attendee(attendee_id):
    """Get event attendee data"""
    return firebase_db.get_event_attendee(attendee_id)

def get_all_event_attendees():
    """Get all event attendees"""
    return firebase_db.get_all_event_attendees()

def get_event_attendees_by_event(event_id):
    """Get attendees for an event"""
    return firebase_db.get_event_attendees_by_event(event_id)

def get_event_registration_by_enrollment(event_id, enrollment_no):
    """Get event registration data by enrollment number for a specific event"""
    return firebase_db.get_event_registration_by_enrollment(event_id, enrollment_no)

def register_attendee_for_event(attendee_id, event_id, registration_data):
    """Register attendee for event"""
    return firebase_db.register_attendee_for_event(attendee_id, event_id, registration_data)

def save_event_attendance(event_id, session_date, attendee_id, attendee_name, status="P"):
    """Save event attendance"""
    return firebase_db.save_event_attendance(event_id, session_date, attendee_id, attendee_name, status)

def get_event_attendance_data(event_id):
    """Get event attendance data"""
    return firebase_db.get_event_attendance_data(event_id)

def update_current_event(event_info):
    """Update current event"""
    return firebase_db.update_current_event(event_info)

def get_current_event():
    """Get current event"""
    return firebase_db.get_current_event()

def get_attendee_by_phone(phone_number):
    """Get attendee by phone number"""
    return firebase_db.get_attendee_by_phone(phone_number)

def delete_event(event_id):
    """Delete event and all associated data"""
    return firebase_db.delete_event(event_id)
