import qrcode
import time
import random
import string
import uuid
import pandas as pd
import openpyxl
import os
import json
from datetime import datetime, timedelta
from flask import Flask, send_file, request, jsonify, render_template, session, redirect, url_for, make_response, flash
from io import BytesIO, StringIO
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Import Firebase functions for events
from firebase_config import (
    firebase_db, save_event_organizer, get_event_organizer, get_all_event_organizers,
    save_event, get_event, get_all_events, get_events_by_organizer,
    save_event_attendee, get_event_attendee, get_event_attendees_by_event, get_all_event_attendees,
    get_event_registration_by_enrollment, register_attendee_for_event, save_event_attendance, get_event_attendance_data,
    update_current_event, get_current_event, get_attendee_by_phone,
    get_active_qr_codes, save_active_qr_code, remove_active_qr_code,
    get_pending_user_info, save_pending_user_info, remove_pending_user_info,
    delete_event
)

app = Flask(__name__)
app.secret_key = 'your_event_attendance_secret_key'

# Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'event_attendance_'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Configuration
QR_EXPIRATION = 30  # seconds

# Authentication decorators
def organizer_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('organizer_logged_in'):
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': 'Session expired. Please login again.', 'redirect': url_for('login')}), 401
            else:
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions
def generate_event_id():
    """Generate a unique event ID"""
    return str(uuid.uuid4())[:8].upper()

def generate_attendee_id():
    """Generate a unique attendee ID"""
    return str(uuid.uuid4())[:12].upper()

def generate_secret_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)).lower()

def get_admin_credentials():
    """Get admin credentials from Firebase"""
    try:
        admin_data = firebase_db.get_admin_data()
        if admin_data and 'credentials' in admin_data:
            return admin_data['credentials']
        else:
            # Create default admin credentials if not exists
            default_credentials = {
                "username": "admin",
                "password": generate_password_hash("admin@123")
            }
            firebase_db.save_admin_data({'credentials': default_credentials})
            return default_credentials
    except Exception as e:
        print(f"Error getting admin credentials: {e}")
        return {
            "username": "admin",
            "password": generate_password_hash("admin@123")
        }

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        
        if user_type == 'organizer':
            username = username.lower()
            organizer = get_event_organizer(username)
            
            if organizer and check_password_hash(organizer['password'], password):
                session.clear()
                session.permanent = True
                session['organizer_logged_in'] = True
                session['organizer_username'] = username
                return redirect(url_for('organizer_dashboard'))
            else:
                flash('Invalid organizer credentials', 'error')
                
        elif user_type == 'admin':
            admin_credentials = get_admin_credentials()
            if (username == admin_credentials['username'] and 
                check_password_hash(admin_credentials['password'], password)):
                session.clear()
                session['admin_logged_in'] = True
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials', 'error')
        else:
            flash('Please select a valid user type', 'error')
            
    return render_template('login.html')

@app.route('/organizer/dashboard')
@organizer_login_required
def organizer_dashboard():
    organizer_username = session.get('organizer_username')
    organizer_info = get_event_organizer(organizer_username)
    if not organizer_info:
        organizer_info = {}
    
    # Get organizer's events
    organizer_events = get_events_by_organizer(organizer_username)
    current_event = get_current_event()
    
    return render_template('organizer/dashboard.html',
                         organizer_info=organizer_info,
                         events=organizer_events,
                         current_event=current_event)

@app.route('/organizer/events/create', methods=['GET', 'POST'])
@organizer_login_required
def create_event():
    # Get organizer information for template context
    organizer_username = session.get('organizer_username')
    organizer_info = get_event_organizer(organizer_username)
    if not organizer_info:
        organizer_info = {}
    
    # Get organizer's past events for registration import option
    past_events = get_events_by_organizer(organizer_username)
    
    if request.method == 'POST':
        
        # Handle max_attendees safely
        max_attendees_str = request.form.get('max_attendees', '').strip()
        max_attendees = None
        if max_attendees_str and max_attendees_str.isdigit():
            max_attendees = int(max_attendees_str)
        
        # Handle geofencing settings
        enable_geofencing = request.form.get('enable_geofencing') == 'on'
        latitude = None
        longitude = None
        geofence_radius = 100  # Default radius
        
        if enable_geofencing:
            try:
                latitude = float(request.form.get('event_latitude', 0))
                longitude = float(request.form.get('event_longitude', 0))
                geofence_radius = int(request.form.get('geofence_radius', 100))
            except (ValueError, TypeError):
                flash('Invalid coordinates provided for geofencing.', 'error')
                return render_template('organizer/create_event.html', organizer_info=organizer_info, past_events=past_events)
        
        event_id = generate_event_id()
        event_data = {
            'event_id': event_id,
            'event_name': request.form.get('event_name'),
            'event_description': request.form.get('event_description'),
            'event_date': request.form.get('event_date'),
            'event_time': request.form.get('event_time'),
            'event_location': request.form.get('event_location'),
            'organizer_id': organizer_username,
            'organizer_name': organizer_info.get('organizer_name', ''),
            'organizer_email': organizer_info.get('organizer_email', ''),
            'organizer_phone': organizer_info.get('organizer_phone', ''),
            'capacity': max_attendees,
            'registration_status': 'open',
            'registration_open': request.form.get('registration_open') == 'on',
            'created_at': datetime.now().isoformat(),
            'status': 'active',
            # Geofencing settings
            'geofencing_enabled': enable_geofencing,
            'latitude': latitude,
            'longitude': longitude,
            'geofence_radius': geofence_radius,
            'one_device_only': request.form.get('one_device_only') == 'on'
        }
        
        if save_event(event_data['event_id'], event_data):
            # Check for import registration request
            import_event_id = request.form.get('import_from_event')
            imported_count = 0
            
            if import_event_id:
                try:
                    # Get attendees from the selected past event
                    past_attendees = get_event_attendees_by_event(import_event_id)
                    
                    if past_attendees:
                        for past_attendee_id, past_attendee_data in past_attendees.items():
                            # Register attendee for the new event
                            # We can reuse the existing attendee ID or generate a new one if needed, 
                            # but usually we want to link the same person.
                            # The register_attendee_for_event function handles getting/creating the attendee record.
                            
                            # However, register_attendee_for_event expects registration_data. 
                            # We need to adapt the past attendee data.
                            
                            registration_data = {
                                'name': past_attendee_data.get('attendee_name', '') or past_attendee_data.get('name', ''),
                                'email': past_attendee_data.get('email', ''),
                                'whatsapp_number': past_attendee_data.get('whatsapp_number', ''),
                                'enrollment_no': past_attendee_data.get('enrollment_no', ''),
                                'school': past_attendee_data.get('school', ''),
                                'branch': past_attendee_data.get('branch', ''),
                                'semester': past_attendee_data.get('semester', ''),
                                'registration_date': datetime.now().isoformat()
                            }
                            
                            # Use existing attendee_id to simplify
                            if register_attendee_for_event(past_attendee_id, event_id, registration_data):
                                imported_count += 1
                                
                except Exception as e:
                    print(f"Error importing registrations: {e}")
                    flash(f'Event created, but error importing registrations: {str(e)}', 'warning')
            
            success_msg = f'Event "{event_data["event_name"]}" created successfully!'
            if enable_geofencing:
                success_msg += ' (Location-based)'
            if imported_count > 0:
                success_msg += f' Imported {imported_count} registrations.'
                
            flash(success_msg, 'success')
            return redirect(url_for('organizer_dashboard'))
        else:
            flash('Error creating event. Please try again.', 'error')
    
    return render_template('organizer/create_event.html', organizer_info=organizer_info, past_events=past_events)

@app.route('/organizer/events/<event_id>/manage')
@organizer_login_required
def manage_event(event_id):
    organizer_username = session.get('organizer_username')
    event_data = get_event(event_id)
    
    if not event_data or event_data.get('organizer_id') != organizer_username:
        # Unauthorized access - redirect silently
        return redirect(url_for('organizer_dashboard'))
    
    # Get organizer information
    organizer_info = get_event_organizer(organizer_username)
    if not organizer_info:
        organizer_info = {}
    
    # Get registered attendees
    attendees_dict = get_event_attendees_by_event(event_id)
    attendees = list(attendees_dict.values()) if attendees_dict else []
    
    # Get attendance records and flatten the nested structure
    attendance_records_dict = get_event_attendance_data(event_id)
    attendance_records = []
    
    if attendance_records_dict:
        for date_key, attendees_for_date in attendance_records_dict.items():
            if isinstance(attendees_for_date, dict):
                for attendee_id, attendee_record in attendees_for_date.items():
                    if isinstance(attendee_record, dict):
                        # Add the flattened attendee record to the list
                        attendance_records.append(attendee_record)

    return render_template('organizer/manage_event.html',
                         event=event_data,
                         attendees=attendees,
                         attendance_records=attendance_records,
                         organizer_info=organizer_info)

@app.route('/organizer/events/<event_id>/start_session', methods=['POST'])
@organizer_login_required
def start_event_session(event_id):
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        if not event_data or event_data.get('organizer_id') != organizer_username:
            return jsonify({'success': False, 'message': 'Event not found or access denied'}), 403
        
        # Set as current active event
        session_start_time = datetime.now().isoformat()
        current_event_info = {
            'event_id': event_id,
            'event_name': event_data['event_name'],
            'organizer_id': organizer_username,
            'session_active': True,
            'session_start_time': session_start_time
        }
        
        update_current_event(current_event_info)
        
        return jsonify({
            'success': True,
            'message': f'Attendance session started for "{event_data["event_name"]}"',
            'qr_url': url_for('display_qr')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/organizer/events/<event_id>/end_session', methods=['POST'])
@organizer_login_required
def end_event_session(event_id):
    try:
        current_event = get_current_event()
        if current_event and current_event.get('event_id') == event_id:
            current_event.update({
                "session_active": False,
                "session_end_time": datetime.now().isoformat()
            })
            update_current_event(current_event)
        
        return jsonify({
            'success': True,
            'message': 'Attendance session ended'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/register/<event_id>', methods=['GET', 'POST'])
def register_for_event(event_id):
    event_data = get_event(event_id)
    if not event_data:
        # Event not found - redirect silently
        return redirect(url_for('index'))
    
    if not event_data.get('registration_open'):
        flash('Registration for this event is closed', 'error')
        return render_template('event_registration.html', event=event_data, registration_closed=True)
    
    # Check if event capacity is full
    capacity = event_data.get('capacity')
    if capacity:  # Only check if capacity is set (not unlimited)
        current_attendees = get_event_attendees_by_event(event_id)
        current_count = len(current_attendees) if current_attendees else 0
        
        if current_count >= capacity:
            flash('Registration slots are full. No more registrations can be accepted.', 'error')
            return render_template('event_registration.html', event=event_data, registration_full=True)
    
    if request.method == 'POST':
        attendee_data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'whatsapp_number': request.form.get('whatsapp_number'),
            'enrollment_no': request.form.get('enrollment_no', '').strip().upper(),
            'school': request.form.get('school', ''),
            'branch': request.form.get('branch', ''),
            'semester': request.form.get('semester', ''),
            'registration_date': datetime.now().isoformat()
        }
        
        # Generate attendee ID
        attendee_id = generate_attendee_id()
        
        # Double-check capacity before processing registration (prevent race conditions)
        capacity = event_data.get('capacity')
        if capacity:  # Only check if capacity is set (not unlimited)
            current_attendees = get_event_attendees_by_event(event_id)
            current_count = len(current_attendees) if current_attendees else 0
            
            if current_count >= capacity:
                flash('Registration slots are full. No more registrations can be accepted.', 'error')
                return render_template('event_registration.html', event=event_data, registration_full=True)
        
        # Check if WhatsApp number is already registered for this event (only if provided)
        whatsapp_number = attendee_data.get('whatsapp_number', '').strip()
        if whatsapp_number:
            existing_attendees = get_event_attendees_by_event(event_id)
            for existing_id, existing_data in existing_attendees.items():
                if existing_data.get('whatsapp_number') == whatsapp_number:
                    flash('This phone number is already registered for this event.', 'error')
                    return render_template('event_registration.html', event=event_data)
        
        # Register attendee
        if register_attendee_for_event(attendee_id, event_id, attendee_data):
            # Registration successful - no flash message needed
            
            # Calculate time until event
            try:
                event_datetime_str = f"{event_data.get('event_date', '')} {event_data.get('event_time', '00:00')}"
                event_datetime = datetime.strptime(event_datetime_str, "%Y-%m-%d %H:%M")
                now = datetime.now()
                time_diff = event_datetime - now
                
                days_until_event = max(0, time_diff.days)
                hours_until_event = max(0, int(time_diff.seconds // 3600)) if time_diff.days >= 0 else 0
                
            except (ValueError, TypeError) as e:
                print(f"Error calculating time until event: {e}")
                days_until_event = 0
                hours_until_event = 0
            
            # Add registration ID and time to attendee data
            attendee_data['registration_id'] = attendee_id
            attendee_data['registration_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return render_template('registration_success.html', 
                                 event=event_data, 
                                 attendee=attendee_data,
                                 days_until_event=days_until_event,
                                 hours_until_event=hours_until_event)
        else:
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('event_registration.html', event=event_data)

@app.route('/api/events/<event_id>/time-slots', methods=['GET'])
def get_time_slots_api(event_id):
    """Get time slots for an event"""
    try:
        slots = firebase_db.get_event_time_slots(event_id)
        return jsonify({'success': True, 'slots': slots})
    except Exception as e:
        print(f"Error getting time slots for event {event_id}: {e}")
        return jsonify({'success': False, 'message': 'Error loading time slots'}), 500

@app.route('/organizer/events/<event_id>/missed-classes')
@organizer_login_required
def view_missed_classes(event_id):
    """View missed classes data for an event"""
    organizer_username = session.get('organizer_username')
    event_data = get_event(event_id)
    
    if not event_data or event_data.get('organizer_id') != organizer_username:
        flash('Unauthorized access', 'error')
        return redirect(url_for('organizer_dashboard'))
    
    # Get all attendees for the event
    attendees = get_event_attendees_by_event(event_id) or {}
    
    # Extract missed classes data
    missed_classes_data = []
    for attendee_id, attendee_data in attendees.items():
        if 'missed_classes' in attendee_data:
            for missed_class in attendee_data['missed_classes']:
                missed_classes_data.append({
                    'student_name': attendee_data.get('name', 'Unknown'),
                    'enrollment_no': attendee_data.get('enrollment_no', 'N/A'),
                    'time_slot': missed_class.get('time_slot', 'N/A'),
                    'subject_code': missed_class.get('subject_code', 'N/A'),
                    'subject_name': missed_class.get('subject_name', 'N/A'),
                    'teacher_name': missed_class.get('teacher_name', 'N/A'),
                    'class_type': missed_class.get('class_type', 'regular'),
                    # Legacy fields for backward compatibility
                    'course_code': missed_class.get('course_code', missed_class.get('subject_code', 'N/A')),
                    'faculty_name': missed_class.get('faculty_name', missed_class.get('teacher_name', 'N/A')),
                    'course_name': missed_class.get('course_name', missed_class.get('subject_name', 'N/A')),
                    'subject_slot': missed_class.get('subject_slot', ''),
                    'lab_slot': missed_class.get('lab_slot', ''),
                    'start_time': missed_class.get('start_time', 'N/A'),
                    'end_time': missed_class.get('end_time', 'N/A')
                })
    
    return render_template('organizer/missed_classes_report.html', 
                         event=event_data, 
                         missed_classes=missed_classes_data)

@app.route('/organizer/events/<event_id>/export-missed-classes')
@organizer_login_required
def export_missed_classes(event_id):
    """Export missed classes data"""
    organizer_username = session.get('organizer_username')
    event_data = get_event(event_id)
    
    if not event_data or event_data.get('organizer_id') != organizer_username:
        flash('Unauthorized access', 'error')
        return redirect(url_for('organizer_dashboard'))
    
    # Get export format
    export_format = request.args.get('format', 'csv')
    
    # Get all attendees for the event
    attendees = get_event_attendees_by_event(event_id) or {}
    
    # Prepare data for export
    export_data = []
    for attendee_id, attendee_data in attendees.items():
        if 'missed_classes' in attendee_data:
            for missed_class in attendee_data['missed_classes']:
                export_data.append({
                    'Student Name': attendee_data.get('name', 'Unknown'),
                    'Enrollment No': attendee_data.get('enrollment_no', 'N/A'),
                    'Email': attendee_data.get('email', 'N/A'),
                    'Time Slot': missed_class.get('time_slot', 'N/A'),
                    'Subject Code': missed_class.get('subject_code', missed_class.get('course_code', 'N/A')),
                    'Subject Name': missed_class.get('subject_name', missed_class.get('course_name', 'N/A')),
                    'Teacher Name': missed_class.get('teacher_name', missed_class.get('faculty_name', 'N/A')),
                    'Class Type': missed_class.get('class_type', 'regular'),
                    'Event': event_data.get('event_name', 'Unknown'),
                    'Event Date': event_data.get('event_date', 'N/A'),
                    'Event Time': event_data.get('event_time', 'N/A')
                })
    
    if not export_data:
        flash('No missed classes data to export', 'info')
        return redirect(url_for('view_missed_classes', event_id=event_id))
    
    # Create DataFrame
    import pandas as pd
    df = pd.DataFrame(export_data)
    
    # Generate filename
    filename = f"missed_classes_{event_data.get('event_name', 'event')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if export_format == 'excel':
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Missed Classes', index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"{filename}.xlsx"
        )
    else:  # CSV format
        from io import StringIO
        output = StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={filename}.csv"
        response.headers["Content-type"] = "text/csv"
        return response

@app.route('/display_qr')
@organizer_login_required
def display_qr():
    current_event = get_current_event()
    if not current_event or not current_event.get('session_active'):
        flash('No active event session. Please start a session first.', 'error')
        return redirect(url_for('organizer_dashboard'))
    
    return render_template('event_qr_display.html', 
                         event=current_event,
                         current_date=datetime.now().strftime("%Y-%m-%d"))

@app.route('/events/<event_id>/qr_display')
@organizer_login_required
def event_qr_display(event_id):
    """Display QR code for a specific event"""
    organizer_username = session.get('organizer_username')
    event_data = get_event(event_id)
    
    if not event_data or event_data.get('organizer_id') != organizer_username:
        # Unauthorized access - redirect silently
        return redirect(url_for('organizer_dashboard'))
    
    return render_template('event_qr_display.html', 
                         event=event_data,
                         current_date=datetime.now().strftime("%Y-%m-%d"))

@app.route('/generate_qr', methods=['GET'])
def generate_qr():
    # Get current event from session or database
    current_event = get_current_event()
    
    if not current_event or not current_event.get('session_active'):
        # Fallback to old WhatsApp method if no active geofenced event
        secret_key = generate_secret_key().lower()
        expiration_time = time.time() + QR_EXPIRATION
        save_active_qr_code(secret_key, expiration_time)
        
        whatsapp_url = f"https://api.whatsapp.com/send?phone=14155238886&text=Event+{secret_key}"
        qr = qrcode.make(whatsapp_url)
    else:
        # Generate QR code pointing to the geofenced attendance page
        event_id = current_event.get('event_id')
        attendance_url = url_for('attend_event', event_id=event_id, _external=True)
        qr = qrcode.make(attendance_url)
    
    qr_io = BytesIO()
    qr.save(qr_io, 'PNG')
    qr_io.seek(0)

    response = send_file(qr_io, mimetype='image/png')
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@admin_login_required
def admin_dashboard():
    try:
        organizers = get_all_event_organizers()
        events = get_all_events()
        
        # Ensure we have valid data structures
        if organizers is None:
            organizers = {}
        if events is None:
            events = {}
        
        # Prepare data for template
        all_organizers = []
        for org_id, org_data in organizers.items():
            # Skip if org_data is None or empty
            if not org_data:
                continue
                
            # Handle different possible field name formats for backward compatibility
            name = (org_data.get('organizer_name') or 
                   org_data.get('name') or 
                   org_data.get('full_name') or 
                   'No Name')
            
            email = (org_data.get('organizer_email') or 
                    org_data.get('email') or 
                    '')
            
            phone = (org_data.get('organizer_phone') or 
                    org_data.get('phone') or 
                    '')
            
            # Calculate event count for this organizer
            event_count = 0
            if events:
                event_count = len([e for e in events.values() if e.get('organizer_id') == org_id])
            
            org_info = {
                'organizer_id': org_id,
                'name': name,
                'email': email,
                'phone': phone,
                'created_at': org_data.get('created_at', ''),
                'event_count': event_count
            }
            all_organizers.append(org_info)
        
        # Pre-compute event attendee counts in memory from cached attendees
        all_attendees = get_all_event_attendees() or {}
        event_counts_map = {}
        for att_id, att_data in all_attendees.items():
            if att_data and isinstance(att_data, dict):
                for eid in att_data.get('registered_events', []):
                    event_counts_map[eid] = event_counts_map.get(eid, 0) + 1

        all_events = []
        total_registrations = 0
        for event_id, event_data in events.items():
            # Skip if event_data is None or empty
            if not event_data:
                continue
                
            reg_count = event_counts_map.get(event_id, 0)
            total_registrations += reg_count
            
            event_info = {
                'event_id': event_id,
                'event_name': event_data.get('event_name', 'Untitled Event'),
                'organizer_name': event_data.get('organizer_name', 'No Organizer'),
                'event_date': event_data.get('event_date', 'TBD'),
                'capacity': event_data.get('capacity', 0),
                'registration_count': reg_count,
                'status': event_data.get('status', 'active')
            }
            all_events.append(event_info)
        
        # Get student statistics
        students = firebase_db.get_all_students()
        
        return render_template('admin/dashboard.html', 
                             all_organizers=all_organizers,
                             all_events=all_events,
                             total_events=len(events),
                             active_events=len([e for e in events.values() if e.get('status') == 'active']),
                             total_organizers=len(organizers),
                             total_students=len(students),
                             total_registrations=total_registrations,
                             current_time=datetime.now().strftime('%Y-%m-%d %H:%M'))
    except Exception as e:
        print(f"ERROR in admin_dashboard: {e}")
        # Even on error, try to get basic student count
        try:
            students = firebase_db.get_all_students()
            student_count = len(students) if students else 0
        except:
            student_count = 0
        
        return render_template('admin/dashboard.html', 
                             all_organizers=[],
                             all_events=[],
                             total_events=0,
                             active_events=0,
                             total_organizers=0,
                             total_students=student_count,
                             total_registrations=0,
                             current_time=datetime.now().strftime('%Y-%m-%d %H:%M'))

# Old function alias - can be removed later
@app.route('/admin/organizers_old')
@admin_login_required
def manage_organizers():
    organizers = get_all_event_organizers()
    return render_template('admin/organizers.html', organizers=organizers)

@app.route('/admin/organizers', methods=['GET', 'POST'])
@admin_login_required
def admin_organizers():
    if request.method == 'POST':
        action = request.form.get('action')
        organizer_id = request.form.get('organizer_id')
        
        if action == 'delete' and organizer_id:
            try:
                # Get organizer data before deletion
                organizer_data = get_event_organizer(organizer_id)
                if organizer_data:
                    # Delete all events created by this organizer
                    created_events = organizer_data.get('created_events', [])
                    for event_id in created_events:
                        delete_event(event_id)
                    
                    # Delete the organizer
                    firebase_db.ref.child('event_organizers').child(organizer_id).delete()
                    flash(f'Organizer "{organizer_data.get("organizer_name", organizer_id)}" and all associated events deleted successfully!', 'success')
                else:
                    flash('Organizer not found!', 'error')
            except Exception as e:
                print(f"Error deleting organizer {organizer_id}: {e}")
                flash('Failed to delete organizer. Please try again.', 'error')
        
        return redirect(url_for('admin_organizers'))
    
    # Get organizers and events data
    organizers = get_all_event_organizers()
    events = get_all_events()
    
    # Calculate event counts for each organizer
    if organizers and events:
        for org_id, org_data in organizers.items():
            if org_data:
                # Calculate actual event count by counting events with matching organizer_id
                event_count = len([e for e in events.values() if e and e.get('organizer_id') == org_id])
                org_data['actual_event_count'] = event_count
    
    return render_template('admin/organizers.html', organizers=organizers)

@app.route('/admin/organizers/add', methods=['GET', 'POST'])
@admin_login_required
def admin_add_organizer():
    if request.method == 'POST':
        username = request.form.get('username', '').lower().strip()
        password = request.form.get('password', '')
        organizer_name = request.form.get('organizer_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # Validation
        if not username or len(username) < 3:
            flash('Username must be at least 3 characters long', 'error')
        elif not password or len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
        elif not organizer_name or len(organizer_name) < 2:
            flash('Please enter a valid full name', 'error')
        elif get_event_organizer(username):
            flash('Organizer username already exists', 'error')
        else:
            new_organizer = {
                "password": generate_password_hash(password),
                "organizer_name": organizer_name,
                "organizer_email": email,
                "organizer_phone": phone,
                "created_events": [],
                "created_at": datetime.now().isoformat()
            }
            
            try:
                if save_event_organizer(username, new_organizer):
                    flash(f'Event organizer "{organizer_name}" added successfully!', 'success')
                    return redirect(url_for('admin_organizers'))
                else:
                    flash('Failed to save organizer to database. Please try again.', 'error')
            except Exception as e:
                print(f"Error creating organizer: {e}")
                flash('An error occurred while creating the organizer. Please try again.', 'error')
    
    return render_template('admin/add_organizer.html')

@app.route('/admin/organizers/<organizer_id>/events')
@admin_login_required
def admin_organizer_events(organizer_id):
    """View all events created by a specific organizer"""
    try:
        organizer_data = get_event_organizer(organizer_id)
        if not organizer_data:
            flash('Organizer not found!', 'error')
            return redirect(url_for('admin_organizers'))
        
        # Get events created by this organizer
        all_events = get_all_events()
        organizer_events = []
        
        for event_id, event_data in all_events.items():
            if event_data.get('organizer_id') == organizer_id:
                # Get attendee count
                attendees = get_event_attendees_by_event(event_id)
                attendee_count = len(attendees) if attendees else 0
                
                event_info = {
                    'event_id': event_id,
                    'event_name': event_data.get('event_name', 'Untitled Event'),
                    'event_date': event_data.get('event_date', 'TBD'),
                    'event_time': event_data.get('event_time', 'TBD'),
                    'event_location': event_data.get('event_location', 'TBD'),
                    'capacity': event_data.get('capacity', 'Unlimited'),
                    'attendee_count': attendee_count,
                    'status': event_data.get('status', 'active'),
                    'registration_status': 'open' if event_data.get('registration_open', True) else 'closed',
                    'created_at': event_data.get('created_at', datetime.now().isoformat()),
                    'geofencing_enabled': event_data.get('geofencing_enabled', False)
                }
                organizer_events.append(event_info)
        
        # Sort by creation date (newest first)
        organizer_events.sort(key=lambda x: x['created_at'], reverse=True)
        
        return render_template('admin/organizer_events.html', 
                             organizer=organizer_data,
                             organizer_id=organizer_id,
                             events=organizer_events)
        
    except Exception as e:
        print(f"Error loading organizer events: {e}")
        flash('Error loading organizer events', 'error')
        return redirect(url_for('admin_organizers'))

@app.route('/admin/organizers/<organizer_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def admin_edit_organizer(organizer_id):
    """Edit organizer details"""
    try:
        organizer_data = get_event_organizer(organizer_id)
        if not organizer_data:
            flash('Organizer not found!', 'error')
            return redirect(url_for('admin_organizers'))
        
        if request.method == 'POST':
            # Get form data
            organizer_name = request.form.get('organizer_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            new_password = request.form.get('new_password', '').strip()
            
            # Validation
            if not organizer_name or len(organizer_name) < 2:
                flash('Please enter a valid full name', 'error')
                return render_template('admin/edit_organizer.html', 
                                     organizer=organizer_data, 
                                     organizer_id=organizer_id)
            
            # Update organizer data
            updated_data = {
                'organizer_name': organizer_name,
                'organizer_email': email,
                'organizer_phone': phone,
                'created_events': organizer_data.get('created_events', []),
                'created_at': organizer_data.get('created_at', datetime.now().isoformat())
            }
            
            # Update password if provided
            if new_password:
                if len(new_password) < 6:
                    flash('Password must be at least 6 characters long', 'error')
                    return render_template('admin/edit_organizer.html', 
                                         organizer=organizer_data, 
                                         organizer_id=organizer_id)
                updated_data['password'] = generate_password_hash(new_password)
            else:
                # Keep existing password
                updated_data['password'] = organizer_data.get('password', '')
            
            # Save updated data
            if save_event_organizer(organizer_id, updated_data):
                flash(f'Organizer "{organizer_name}" updated successfully!', 'success')
                return redirect(url_for('admin_organizers'))
            else:
                flash('Failed to update organizer. Please try again.', 'error')
        
        return render_template('admin/edit_organizer.html', 
                             organizer=organizer_data, 
                             organizer_id=organizer_id)
        
    except Exception as e:
        print(f"Error editing organizer: {e}")
        flash('Error editing organizer', 'error')
        return redirect(url_for('admin_organizers'))

@app.route('/organizer/logout')
def organizer_logout():
    organizer_username = session.get('organizer_username')
    if organizer_username:
        # End current event session if active
        current_event = get_current_event()
        if current_event and current_event.get('organizer_id') == organizer_username:
            current_event.update({
                "session_active": False,
                "session_end_time": datetime.now().isoformat()
            })
            update_current_event(current_event)
    
    session.clear()
    return redirect(url_for('login'))

# Admin Student Management Routes
@app.route('/admin/students', methods=['GET', 'POST'])
@admin_login_required
def admin_students():
    if request.method == 'POST':
        action = request.form.get('action')
        enrollment_no = request.form.get('enrollment_no')
        
        if action == 'delete' and enrollment_no:
            try:
                student_data = firebase_db.get_student_by_enrollment(enrollment_no)
                if student_data:
                    firebase_db.delete_student(enrollment_no)
                    flash(f'Student "{student_data.get("student_name", enrollment_no)}" deleted successfully!', 'success')
                else:
                    flash('Student not found!', 'error')
            except Exception as e:
                print(f"Error deleting student {enrollment_no}: {e}")
                flash('Failed to delete student. Please try again.', 'error')
        
        return redirect(url_for('admin_students'))
    
    # Handle search and filtering
    search_query = request.args.get('search', '').strip()
    school_filter = request.args.get('school', '').strip()
    branch_filter = request.args.get('branch', '').strip()
    
    if search_query:
        students = firebase_db.search_students_by_name(search_query)
    elif school_filter or branch_filter:
        students = firebase_db.get_students_by_school_branch(school_filter, branch_filter)
    else:
        students = firebase_db.get_all_students()
    
    # Get unique schools and branches for filter dropdowns
    all_students = firebase_db.get_all_students()
    schools = sorted(set(s.get('school', '') for s in all_students.values() if s.get('school')))
    branches = sorted(set(s.get('branch', '') for s in all_students.values() if s.get('branch')))
    
    return render_template('admin/students.html', 
                         students=students, 
                         schools=schools, 
                         branches=branches,
                         search_query=search_query,
                         school_filter=school_filter,
                         branch_filter=branch_filter)

@app.route('/admin/students/add', methods=['GET', 'POST'])
@admin_login_required
def admin_add_student():
    if request.method == 'POST':
        enrollment_no = request.form.get('enrollment_no', '').strip().upper()
        student_name = request.form.get('student_name', '').strip()
        school = request.form.get('school', '').strip()
        branch = request.form.get('branch', '').strip()
        semester = request.form.get('semester', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        year_of_admission = request.form.get('year_of_admission', '').strip()
        
        # Validation
        if not enrollment_no or len(enrollment_no) < 3:
            flash('Enrollment number must be at least 3 characters long', 'error')
        elif not student_name or len(student_name) < 2:
            flash('Please enter a valid student name', 'error')
        elif not school:
            flash('Please enter the school/college name', 'error')
        elif not branch:
            flash('Please enter the branch/department', 'error')
        elif firebase_db.get_student_by_enrollment(enrollment_no):
            flash('Student with this enrollment number already exists', 'error')
        else:
            new_student = {
                "student_name": student_name,
                "school": school,
                "branch": branch,
                "semester": semester,
                "email": email,
                "phone": phone,
                "year_of_admission": year_of_admission,
                "created_at": datetime.now().isoformat(),
                "status": "active"
            }
            
            try:
                if firebase_db.save_student_info(enrollment_no, new_student):
                    flash(f'Student "{student_name}" added successfully!', 'success')
                    return redirect(url_for('admin_students'))
                else:
                    flash('Failed to save student to database. Please try again.', 'error')
            except Exception as e:
                print(f"Error creating student: {e}")
                flash('An error occurred while creating the student. Please try again.', 'error')
    
    return render_template('admin/add_student.html')

@app.route('/debug/organizers')
@admin_login_required
def debug_organizers():
    """Debug route to check organizer data structure"""
    try:
        organizers = get_all_event_organizers()
        events = get_all_events()
        
        debug_info = {
            'firebase_connected': firebase_db.ref is not None,
            'organizers_count': len(organizers) if organizers else 0,
            'events_count': len(events) if events else 0,
            'organizers': [],
            'events': []
        }
        
        # Debug organizers
        if organizers:
            for org_id, org_data in organizers.items():
                name = (org_data.get('organizer_name') or 
                       org_data.get('name') or 
                       org_data.get('full_name') or 
                       'No Name')
                
                email = (org_data.get('organizer_email') or 
                        org_data.get('email') or 
                        '')
                
                phone = (org_data.get('organizer_phone') or 
                        org_data.get('phone') or 
                        '')
                
                debug_info['organizers'].append({
                    'org_id': org_id,
                    'raw_data': org_data,
                    'available_keys': list(org_data.keys()) if org_data else [],
                    'resolved_name': name,
                    'resolved_email': email,
                    'resolved_phone': phone
                })
        
        # Debug events
        if events:
            for event_id, event_data in events.items():
                debug_info['events'].append({
                    'event_id': event_id,
                    'raw_data': event_data,
                    'available_keys': list(event_data.keys()) if event_data else [],
                    'event_name': event_data.get('event_name', 'Untitled Event'),
                    'organizer_name': event_data.get('organizer_name', 'No Organizer'),
                    'organizer_id': event_data.get('organizer_id', '')
                })
        
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e), 'error_type': type(e).__name__}), 500

@app.route('/admin/fix-data')
@admin_login_required  
def fix_organizer_data():
    """Fix organizer data inconsistencies and repair missing event organizer info"""
    try:
        organizers = get_all_event_organizers()
        events = get_all_events()
        
        fixed_organizers = 0
        fixed_events = 0
        
        # Fix organizer data format
        for org_id, org_data in organizers.items():
            needs_fix = False
            updated_data = dict(org_data) if org_data else {}
            
            # Convert old format to new format
            if 'name' in org_data and 'organizer_name' not in org_data:
                updated_data['organizer_name'] = org_data['name']
                needs_fix = True
            
            if 'email' in org_data and 'organizer_email' not in org_data:
                updated_data['organizer_email'] = org_data['email']
                needs_fix = True
                
            if 'phone' in org_data and 'organizer_phone' not in org_data:
                updated_data['organizer_phone'] = org_data['phone']
                needs_fix = True
            
            if needs_fix:
                save_event_organizer(org_id, updated_data)
                fixed_organizers += 1
        
        # Fix events missing organizer information
        for event_id, event_data in events.items():
            organizer_id = event_data.get('organizer_id')
            if organizer_id and organizer_id in organizers:
                organizer_info = organizers[organizer_id]
                
                needs_event_fix = False
                updated_event_data = dict(event_data)
                
                # Add missing organizer name
                if not event_data.get('organizer_name') and organizer_info.get('organizer_name'):
                    updated_event_data['organizer_name'] = organizer_info['organizer_name']
                    needs_event_fix = True
                
                # Add missing organizer email
                if not event_data.get('organizer_email') and organizer_info.get('organizer_email'):
                    updated_event_data['organizer_email'] = organizer_info['organizer_email']
                    needs_event_fix = True
                
                # Add missing organizer phone
                if not event_data.get('organizer_phone') and organizer_info.get('organizer_phone'):
                    updated_event_data['organizer_phone'] = organizer_info['organizer_phone']
                    needs_event_fix = True
                
                if needs_event_fix:
                    updated_event_data['updated_at'] = datetime.now().isoformat()
                    save_event(event_id, updated_event_data)
                    fixed_events += 1
        
        return jsonify({
            'success': True,
            'message': f'Fixed {fixed_organizers} organizer records and {fixed_events} event records',
            'organizers_processed': len(organizers),
            'events_processed': len(events),
            'organizers_fixed': fixed_organizers,
            'events_fixed': fixed_events
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/students/<enrollment_no>/edit', methods=['GET', 'POST'])
@admin_login_required
def admin_edit_student(enrollment_no):
    student_data = firebase_db.get_student_by_enrollment(enrollment_no)
    if not student_data:
        flash('Student not found', 'error')
        return redirect(url_for('admin_students'))
    
    if request.method == 'POST':
        student_name = request.form.get('student_name', '').strip()
        school = request.form.get('school', '').strip()
        branch = request.form.get('branch', '').strip()
        semester = request.form.get('semester', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        year_of_admission = request.form.get('year_of_admission', '').strip()
        
        # Validation
        if not student_name or len(student_name) < 2:
            flash('Please enter a valid student name', 'error')
        elif not school:
            flash('Please enter the school/college name', 'error')
        elif not branch:
            flash('Please enter the branch/department', 'error')
        else:
            updated_student = {
                "student_name": student_name,
                "school": school,
                "branch": branch,
                "semester": semester,
                "email": email,
                "phone": phone,
                "year_of_admission": year_of_admission,
                "updated_at": datetime.now().isoformat()
            }
            
            try:
                if firebase_db.update_student_info(enrollment_no, updated_student):
                    flash(f'Student "{student_name}" updated successfully!', 'success')
                    return redirect(url_for('admin_students'))
                else:
                    flash('Failed to update student. Please try again.', 'error')
            except Exception as e:
                print(f"Error updating student: {e}")
                flash('An error occurred while updating the student. Please try again.', 'error')
    
    return render_template('admin/edit_student.html', student=student_data, enrollment_no=enrollment_no)

# Excel Import Routes
@app.route('/admin/students/import', methods=['GET', 'POST'])
@admin_login_required
def admin_import_students():
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['excel_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            try:
                # Read Excel file
                df = pd.read_excel(file)
                
                # Validate required columns
                required_columns = ['enrollment_no', 'student_name', 'school', 'branch']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    flash(f'Missing required columns: {", ".join(missing_columns)}', 'error')
                    return render_template('admin/import_students.html')
                
                # Process and validate data
                success_count = 0
                error_count = 0
                errors = []
                
                for index, row in df.iterrows():
                    try:
                        # Clean and validate enrollment number
                        enrollment_no = str(row['enrollment_no']).strip().upper()
                        if len(enrollment_no) < 3:
                            errors.append(f"Row {index + 2}: Invalid enrollment number '{enrollment_no}'")
                            error_count += 1
                            continue
                        
                        # Check if student already exists
                        if firebase_db.get_student_by_enrollment(enrollment_no):
                            errors.append(f"Row {index + 2}: Student '{enrollment_no}' already exists")
                            error_count += 1
                            continue
                        
                        # Prepare student data
                        student_data = {
                            "student_name": str(row['student_name']).strip(),
                            "school": str(row['school']).strip(),
                            "branch": str(row['branch']).strip(),
                            "semester": str(row.get('semester', '')).strip(),
                            "email": str(row.get('email', '')).strip(),
                            "phone": str(row.get('phone', '')).strip(),
                            "year_of_admission": str(row.get('year_of_admission', '')).strip(),
                            "created_at": datetime.now().isoformat(),
                            "status": "active",
                            "imported_via": "excel"
                        }
                        
                        # Validate required fields
                        if not student_data['student_name'] or len(student_data['student_name']) < 2:
                            errors.append(f"Row {index + 2}: Invalid student name")
                            error_count += 1
                            continue
                        
                        if not student_data['school']:
                            errors.append(f"Row {index + 2}: School/college is required")
                            error_count += 1
                            continue
                        
                        if not student_data['branch']:
                            errors.append(f"Row {index + 2}: Branch/department is required")
                            error_count += 1
                            continue
                        
                        # Save to database
                        if firebase_db.save_student_info(enrollment_no, student_data):
                            success_count += 1
                        else:
                            errors.append(f"Row {index + 2}: Failed to save student '{enrollment_no}'")
                            error_count += 1
                            
                    except Exception as e:
                        errors.append(f"Row {index + 2}: Error processing - {str(e)}")
                        error_count += 1
                
                # Show results
                if success_count > 0:
                    flash(f'Successfully imported {success_count} students!', 'success')
                
                if error_count > 0:
                    flash(f'{error_count} errors occurred during import.', 'error')
                    
                    # Show first 10 errors
                    for error in errors[:10]:
                        flash(error, 'error')
                    
                    if len(errors) > 10:
                        flash(f'... and {len(errors) - 10} more errors.', 'error')
                
                return redirect(url_for('admin_students'))
                
            except Exception as e:
                flash(f'Error processing Excel file: {str(e)}', 'error')
                return render_template('admin/import_students.html')
        else:
            flash('Invalid file type. Please upload an Excel file (.xlsx or .xls)', 'error')
    
    return render_template('admin/import_students.html')

@app.route('/admin/students/template')
@admin_login_required
def download_student_template():
    """Download Excel template for student import"""
    try:
        # Create sample data
        template_data = {
            'enrollment_no': ['CS2021001', 'IT2021002', 'ECE2021003'],
            'student_name': ['John Doe', 'Jane Smith', 'Alex Johnson'],
            'school': ['ABC College of Engineering', 'ABC College of Engineering', 'XYZ Institute of Technology'],
            'branch': ['Computer Science Engineering', 'Information Technology', 'Electronics and Communication'],
            'semester': ['5', '6', '4'],
            'email': ['john.doe@example.com', 'jane.smith@example.com', 'alex.johnson@example.com'],
            'phone': ['+91 9876543210', '+91 9876543211', '+91 9876543212'],
            'year_of_admission': ['2021', '2021', '2021']
        }
        
        df = pd.DataFrame(template_data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Students')
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Students']
            
            # Add formatting
            from openpyxl.styles import Font, PatternFill
            
            # Header styling
            header_font = Font(bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
            
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 30)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='student_import_template.xlsx'
        )
        
    except Exception as e:
        flash(f'Error generating template: {str(e)}', 'error')
        return redirect(url_for('admin_students'))

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# API endpoint for student lookup during event registration
@app.route('/api/student/<enrollment_no>')
def get_student_data(enrollment_no):
    """API endpoint to get student data for auto-filling registration forms"""
    try:
        student_data = firebase_db.get_student_by_enrollment(enrollment_no.upper().strip())
        if student_data:
            # Return only necessary data for registration
            return jsonify({
                'success': True,
                'student': {
                    'name': student_data.get('student_name', ''),
                    'school': student_data.get('school', ''),
                    'branch': student_data.get('branch', ''),
                    'semester': student_data.get('semester', ''),
                    'email': student_data.get('email', ''),
                    'phone': student_data.get('phone', '')
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Student not found'
            })
    except Exception as e:
        print(f"Error fetching student data: {e}")
        return jsonify({
            'success': False,
            'message': 'Error retrieving student data'
        })

@app.route('/api/event/<event_id>/registration/<enrollment_no>')
def get_event_registration_data(event_id, enrollment_no):
    """API endpoint to get event registration data for attendance marking by enrollment number"""
    try:
        registration_data = get_event_registration_by_enrollment(event_id, enrollment_no.upper().strip())
        if registration_data:
            return jsonify({
                'success': True,
                'registration': {
                    'attendee_id': registration_data.get('attendee_id', ''),
                    'name': registration_data.get('name', ''),
                    'enrollment_no': registration_data.get('enrollment_no', ''),
                    'school': registration_data.get('school', ''),
                    'branch': registration_data.get('branch', ''),
                    'semester': registration_data.get('semester', ''),
                    'whatsapp_number': registration_data.get('whatsapp_number', ''),
                    'email': registration_data.get('email', '')
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No registration found for this enrollment number in this event'
            })
    except Exception as e:
        print(f"Error fetching registration data: {e}")
        return jsonify({
            'success': False,
            'message': 'Error retrieving registration data'
        })

@app.route('/api/events/<event_id>/geofencing', methods=['POST'])
@organizer_login_required
def update_event_geofencing(event_id):
    """Update event geofencing location and settings"""
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        # Check if event exists and user has permission
        if not event_data or event_data.get('organizer_id') != organizer_username:
            return jsonify({
                'success': False,
                'message': 'Event not found or you do not have permission to edit it'
            }), 403
        
        # Get form data
        event_location = request.form.get('event_location', '').strip()
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()
        geofence_radius = request.form.get('geofence_radius', '').strip()
        
        # Validate geofence radius
        if geofence_radius:
            try:
                radius = int(geofence_radius)
                if radius < 10 or radius > 1000:
                    return jsonify({
                        'success': False,
                        'message': 'Geofence radius must be between 10 and 1000 meters'
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid geofence radius value'
                }), 400
        
        # Validate coordinates if provided
        if latitude or longitude:
            try:
                if latitude and longitude:
                    lat = float(latitude)
                    lng = float(longitude)
                    
                    # Basic coordinate validation
                    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                        return jsonify({
                            'success': False,
                            'message': 'Invalid coordinates. Latitude must be between -90 and 90, longitude between -180 and 180'
                        }), 400
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Both latitude and longitude are required'
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid coordinate values. Please enter valid numbers'
                }), 400
        
        # Update geofencing status from checkbox
        enable_geofencing = request.form.get('enable_geofencing') == 'on' or request.form.get('enable_geofencing') == 'true'
        updated_data['geofencing_enabled'] = enable_geofencing

        if not enable_geofencing:
            # If turned off, remove coordinates so location is never required
            updated_data['latitude'] = None
            updated_data['longitude'] = None
        else:
            if latitude and longitude:
                updated_data['latitude'] = float(latitude)
                updated_data['longitude'] = float(longitude)
            if geofence_radius:
                updated_data['geofence_radius'] = int(geofence_radius)

        if event_location:
            updated_data['event_location'] = event_location

        # Save updated event
        if save_event(event_id, updated_data):
            return jsonify({
                'success': True,
                'message': 'Geofencing settings updated successfully!',
                'data': {
                    'geofencing_enabled': updated_data.get('geofencing_enabled'),
                    'event_location': updated_data.get('event_location'),
                    'latitude': updated_data.get('latitude'),
                    'longitude': updated_data.get('longitude'),
                    'geofence_radius': updated_data.get('geofence_radius')
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to save changes. Please try again.'
            }), 500
        
    except Exception as e:
        print(f"Error updating geofencing: {e}")
        return jsonify({
            'success': False,
            'message': 'Server error occurred. Please try again.'
        }), 500

# Export Routes
@app.route('/export/attendees/<event_id>')
@organizer_login_required
def export_attendees(event_id):
    """Export event attendees list"""
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        # Check permissions
        if not event_data or event_data.get('organizer_id') != organizer_username:
            # Unauthorized access - redirect silently
            return redirect(url_for('organizer_dashboard'))
        
        # Get attendees data
        attendees_dict = get_event_attendees_by_event(event_id)
        attendees = list(attendees_dict.values()) if attendees_dict else []
        
        if not attendees:
            flash('No attendees found for this event.', 'warning')
            return redirect(url_for('manage_event', event_id=event_id))
        
        # Create DataFrame
        export_data = []
        for attendee in attendees:
            export_data.append({
                'Sl No': len(export_data) + 1,
                'NAME': attendee.get('attendee_name', attendee.get('name', '')),
                'ENROLLMENT NUMBER': attendee.get('enrollment_no', ''),
                'SCHOOL': attendee.get('school', ''),
                'PROGRAM': attendee.get('branch', ''),
                'SEMESTER': attendee.get('semester', ''),
                'EMAIL': attendee.get('email', ''),
                'WHATSAPP NUMBER': attendee.get('whatsapp_number', ''),
                'REGISTRATION DATE': attendee.get('registration_date', '')
            })
        
        df = pd.DataFrame(export_data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Attendees', index=False)
        
        output.seek(0)
        
        # Prepare filename
        event_name = event_data.get('event_name', 'Event').replace(' ', '_')
        filename = f"{event_name}_Attendees_List.xlsx"
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"Error exporting attendees: {e}")
        flash('Error exporting attendees. Please try again.', 'error')
        return redirect(url_for('manage_event', event_id=event_id))

@app.route('/export/attendance/<event_id>')
@organizer_login_required
def export_attendance(event_id):
    """Export event attendance records with full student details"""
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        # Check permissions
        if not event_data or event_data.get('organizer_id') != organizer_username:
            # Unauthorized access - redirect silently
            return redirect(url_for('organizer_dashboard'))
        
        # Get attendance records
        attendance_dict = get_event_attendance_data(event_id)
        print(f"DEBUG: attendance_dict = {attendance_dict}")
        
        if not attendance_dict:
            # No attendance records - return empty file or redirect silently
            print("DEBUG: No attendance records found")
            return redirect(url_for('manage_event', event_id=event_id))
        
        # Create comprehensive attendance data
        export_data = []
        sl_no = 1
        
        # Process the nested attendance structure - export ALL attendance records
        for record_key, attendees_dict in attendance_dict.items():
                
            # Process each attendee in this date record
            if isinstance(attendees_dict, dict):
                for attendee_id, record in attendees_dict.items():
                    if not isinstance(record, dict):
                        continue
                        
                    # Get enrollment number from record
                    enrollment_no = record.get('enrollment_no', attendee_id)
                    attendee_name = record.get('attendee_name', record.get('name', ''))
                    attendee_phone = record.get('whatsapp_number', record.get('attendee_phone', ''))
                    
                    # Get student details directly from attendance record (now includes registration data)
                    student_details = {
                        'SCHOOL': record.get('school', ''),
                        'PROGRAM': record.get('branch', ''),
                        'SEMESTER': record.get('semester', ''),
                        'EMAIL': record.get('email', ''),
                        'PHONE': record.get('whatsapp_number', record.get('attendee_phone', ''))
                    }
                    
                    # If attendance record doesn't have complete data, try registration lookup
                    if not student_details.get('SCHOOL') and enrollment_no:
                        try:
                            registration_data = get_event_registration_by_enrollment(event_id, enrollment_no)
                        except:
                            registration_data = None
                        if registration_data:
                            student_details = {
                                'SCHOOL': registration_data.get('school', ''),
                                'PROGRAM': registration_data.get('branch', ''),
                                'SEMESTER': registration_data.get('semester', ''),
                                'EMAIL': registration_data.get('email', ''),
                                'PHONE': registration_data.get('whatsapp_number', '')
                            }
                            # Use registration data for better accuracy
                            attendee_name = registration_data.get('name', attendee_name)
                            attendee_phone = registration_data.get('whatsapp_number', attendee_phone)
                    
                    # Parse attendance timestamp
                    attendance_time = record.get('marked_at', record.get('timestamp', ''))
                    try:
                        if attendance_time:
                            dt = datetime.fromisoformat(attendance_time.replace('Z', '+00:00'))
                            formatted_date = dt.strftime('%d/%m/%Y')
                            formatted_time = dt.strftime('%H:%M:%S')
                        else:
                            formatted_date = 'N/A'
                            formatted_time = 'N/A'
                    except:
                        formatted_date = 'N/A'
                        formatted_time = 'N/A'
                    
                    # Process missed classes data
                    missed_classes = record.get('missed_classes', [])
                    missed_classes_summary = []
                    
                    if missed_classes and isinstance(missed_classes, list):
                        for missed_class in missed_classes:
                            if isinstance(missed_class, dict):
                                time_slot = missed_class.get('time_slot', 'N/A')
                                subject_code = missed_class.get('subject_code', 'N/A')
                                subject_name = missed_class.get('subject_name', 'N/A')
                                teacher_name = missed_class.get('teacher_name', 'N/A')
                                
                                # Create a summary string for this missed class
                                class_summary = f"{time_slot}: {subject_code}"
                                if subject_name and subject_name != 'N/A':
                                    class_summary += f" ({subject_name})"
                                if teacher_name and teacher_name != 'N/A':
                                    class_summary += f" - {teacher_name}"
                                
                                missed_classes_summary.append(class_summary)
                    
                    # Join all missed classes into one field, or mark as None if no missed classes
                    missed_classes_text = '; '.join(missed_classes_summary) if missed_classes_summary else 'None'
                    
                    export_data.append({
                        'Sl No': sl_no,
                        'NAME': attendee_name,
                        'ENROLLMENT NUMBER': enrollment_no or 'N/A',
                        'SCHOOL': student_details.get('SCHOOL', 'N/A'),
                        'PROGRAM': student_details.get('PROGRAM', 'N/A'),
                        'SEMESTER': student_details.get('SEMESTER', 'N/A'),
                        'EMAIL': student_details.get('EMAIL', 'N/A'),
                        'PHONE': student_details.get('PHONE', record.get('attendee_phone', 'N/A')),
                        'DATE': formatted_date,
                        'TIME': formatted_time,
                        'STATUS': 'PRESENT',
                        'MISSED CLASSES': missed_classes_text
                    })
                    sl_no += 1
        
        if not export_data:
            # No records for criteria - redirect silently
            return redirect(url_for('manage_event', event_id=event_id))
        
        df = pd.DataFrame(export_data)
        
        # Create detailed missed classes data for separate sheet
        detailed_missed_classes = []
        missed_class_sl_no = 1
        
        for record_key, attendees_dict in attendance_dict.items():
                
            if isinstance(attendees_dict, dict):
                for attendee_id, record in attendees_dict.items():
                    if not isinstance(record, dict):
                        continue
                        
                    enrollment_no = record.get('enrollment_no', attendee_id)
                    attendee_name = record.get('attendee_name', record.get('name', ''))
                    missed_classes = record.get('missed_classes', [])
                    
                    if missed_classes and isinstance(missed_classes, list):
                        for missed_class in missed_classes:
                            if isinstance(missed_class, dict):
                                detailed_missed_classes.append({
                                    'Sl No': missed_class_sl_no,
                                    'Student Name': attendee_name,
                                    'Enrollment Number': enrollment_no or 'N/A',
                                    'Time Slot': missed_class.get('time_slot', 'N/A'),
                                    'Subject Code': missed_class.get('subject_code', 'N/A'),
                                    'Subject Name': missed_class.get('subject_name', 'N/A'),
                                    'Teacher Name': missed_class.get('teacher_name', 'N/A'),
                                    'Class Type': missed_class.get('class_type', 'regular')
                                })
                                missed_class_sl_no += 1
        
        # Create Excel file with multiple sheets
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Main attendance sheet
            df.to_excel(writer, sheet_name='Attendance', index=False)
            
            # Detailed missed classes sheet
            if detailed_missed_classes:
                missed_classes_df = pd.DataFrame(detailed_missed_classes)
                missed_classes_df.to_excel(writer, sheet_name='Missed Classes Details', index=False)
            
            # Summary sheet
            summary_data = {
                'Event Name': [event_data.get('event_name', 'N/A')],
                'Event Date': [event_data.get('event_date', 'N/A')],
                'Event Location': [event_data.get('event_location', 'N/A')],
                'Total Present': [len(export_data)],
                'Total Missed Classes': [len(detailed_missed_classes)],
                'Students with Missed Classes': [len(set(mc['Student Name'] for mc in detailed_missed_classes)) if detailed_missed_classes else 0],
                'Export Date': [datetime.now().strftime('%d/%m/%Y %H:%M:%S')],
                'Exported By': [organizer_username]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        output.seek(0)
        
        # Prepare filename
        event_name = event_data.get('event_name', 'Event').replace(' ', '_')
        date_suffix = f"_{datetime.now().strftime('%Y%m%d')}"
        filename = f"{event_name}_Attendance{date_suffix}.xlsx"
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"Error exporting attendance: {e}")
        import traceback
        traceback.print_exc()
        
        # Return a simple error response instead of redirect for debugging
        return jsonify({
            'success': False, 
            'error': str(e),
            'message': 'Error exporting attendance. Check console for details.'
        }), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('login'))

# Geofenced Attendance Routes
@app.route('/event/<event_id>/attend')
def attend_event(event_id):
    """Display geofenced attendance page for an event"""
    event_data = get_event(event_id)
    if not event_data:
        # Event not found - redirect silently
        return redirect(url_for('index'))
    
    # Check if event is active
    if event_data.get('status') != 'active':
        flash('This event is no longer active', 'error')
        return render_template('event_error.html', 
                             message='This event is no longer active',
                             event=event_data)
    
    return render_template('geofenced_attendance.html', event=event_data)

@app.route('/event/<event_id>/qr')
def event_qr_code(event_id):
    """Generate QR code specifically for an event's attendance page"""
    event_data = get_event(event_id)
    if not event_data:
        return "Event not found", 404
    
    # Generate QR code pointing directly to the event attendance page
    attendance_url = url_for('attend_event', event_id=event_id, _external=True)
    qr = qrcode.make(attendance_url)
    qr_io = BytesIO()
    qr.save(qr_io, 'PNG')
    qr_io.seek(0)

    response = send_file(qr_io, mimetype='image/png')
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

@app.route('/mark_geofenced_attendance', methods=['POST'])
def mark_geofenced_attendance():
    """Handle geofenced attendance marking with device validation"""
    try:
        data = request.get_json()
        
        # Extract data from request
        event_id = data.get('event_id')
        student_name = data.get('student_name')
        student_id = data.get('student_id')  # This is now the attendee_id from registration
        enrollment_no = data.get('enrollment_no')
        whatsapp_number = data.get('whatsapp_number')
        device_signature = data.get('device_signature')
        location_data = data.get('location')
        missed_classes = data.get('missed_classes', [])  # Extract missed classes data
        
        # Debug logging
        print(f"DEBUG: Received attendance data:")
        print(f"  - Event ID: {event_id}")
        print(f"  - Student Name: {student_name}")
        print(f"  - Enrollment No: {enrollment_no}")
        print(f"  - Missed Classes: {missed_classes}")
        print(f"  - Missed Classes Type: {type(missed_classes)}")
        print(f"  - Missed Classes Length: {len(missed_classes) if isinstance(missed_classes, list) else 'N/A'}")
        
        # Validation
        if not all([event_id, student_name, student_id, enrollment_no, device_signature]):
            return jsonify({
                'success': False,
                'message': 'Missing required data'
            }), 400

        # Handle On-the-fly Registration
        if data.get('register_on_the_fly'):
            print(f"DEBUG: Performing on-the-fly registration for {enrollment_no}")
            reg_data = {
                'name': student_name,
                'email': data.get('email'),
                'whatsapp_number': whatsapp_number,
                'enrollment_no': enrollment_no,
                'school': data.get('school'),
                'branch': data.get('branch'),
                'semester': data.get('semester'),
                'registration_date': datetime.now().isoformat(),
                'on_the_fly': True
            }
            
            # Generate a new attendee ID
            new_attendee_id = generate_attendee_id()
            
            # Register the student for the event
            if register_attendee_for_event(new_attendee_id, event_id, reg_data):
                # Update student_id to the new one for attendance marking
                student_id = new_attendee_id
                print(f"DEBUG: On-the-fly registration successful: {student_id}")
            else:
                return jsonify({
                    'success': False,
                    'message': 'Automatic registration failed'
                }), 400

        # Get event details
        event_data = get_event(event_id)

        if not event_data:
            return jsonify({
                'success': False,
                'message': 'Event not found'
            }), 404
        
        # Check if event is active
        if event_data.get('status') != 'active':
            return jsonify({
                'success': False,
                'message': 'Event is not active'
            }), 400
        
        # Validate geofence ONLY IF geofencing is enabled AND event has coordinates configured
        is_geofencing_active = event_data.get('geofencing_enabled', False) and bool(event_data.get('latitude')) and bool(event_data.get('longitude'))
        if is_geofencing_active:
            if not location_data or not location_data.get('lat') or not location_data.get('lng'):
                return jsonify({
                    'success': False,
                    'message': 'Location access is required for this event. Please enable GPS and allow location access.'
                }), 400

            geofence_radius = event_data.get('geofence_radius', 100)  # Default 100m
            within_geofence, distance = firebase_db.validate_geofence(
                location_data.get('lat'),
                location_data.get('lng'),
                event_data.get('latitude'),
                event_data.get('longitude'),
                geofence_radius
            )
            
            if not within_geofence:
                return jsonify({
                    'success': False,
                    'message': f'You are {round(distance)}m away from the event location. Please move closer (within {geofence_radius}m).'
                }), 400
        
        # Create attendee data (based on registration data)
        attendee_data = {
            'attendee_id': student_id,
            'attendee_name': student_name,
            'name': student_name,
            'enrollment_no': enrollment_no,
            'whatsapp_number': whatsapp_number,
            'attendance_via_registration': True,
            'registered_at': datetime.now().isoformat(),
            'missed_classes': missed_classes  # Include missed classes in attendance data
        }
        
        # Save geofenced attendance
        success, message = firebase_db.save_geofenced_attendance(
            event_id,
            attendee_data,
            device_signature,
            location_data,
            request.remote_addr
        )
        
        if success:
            # DON'T save attendee info again as it might overwrite registration data
            # The attendance record already contains all necessary info
            
            return jsonify({
                'success': True,
                'message': message,
                'attendee_name': student_name,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        print(f"Error in mark_geofenced_attendance: {e}")
        return jsonify({
            'success': False,
            'message': 'Server error occurred. Please try again.'
        }), 500

@app.route('/debug/attendance/<event_id>')
def debug_attendance(event_id):
    """Debug route to check attendance data"""
    try:
        # Get attendance records
        attendance_data = get_event_attendance_data(event_id)
        
        # Get attendees (registered users)
        attendees_data = get_event_attendees_by_event(event_id)
        
        debug_info = {
            'event_id': event_id,
            'attendance_records': attendance_data,
            'registered_attendees': attendees_data,
            'attendance_count': len(attendance_data) if attendance_data else 0,
            'registered_count': len(attendees_data) if attendees_data else 0
        }
        
        return f"<pre>{json.dumps(debug_info, indent=2, default=str)}</pre>"
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/attendance_success')
def attendance_success():
    """Success page after marking attendance"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Attendance Marked</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; 
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .success-container { background: white; padding: 40px; border-radius: 15px; 
                               max-width: 400px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
            .success-icon { font-size: 80px; margin-bottom: 20px; }
            .success-title { color: #333; font-size: 24px; margin-bottom: 15px; }
            .success-message { color: #666; font-size: 16px; }
        </style>
    </head>
    <body>
        <div class="success-container">
            <div class="success-icon">🎉</div>
            <h1 class="success-title">Attendance Marked!</h1>
            <p class="success-message">Your attendance has been successfully recorded. You can now close this page.</p>
        </div>
    </body>
    </html>
    """

@app.route('/event/<event_id>/attendance_stats')
@organizer_login_required
def event_attendance_stats(event_id):
    """View attendance statistics for an event with location and device data"""
    organizer_username = session.get('organizer_username')
    event_data = get_event(event_id)
    
    if not event_data or event_data.get('organizer_id') != organizer_username:
        # Unauthorized access - redirect silently
        return redirect(url_for('organizer_dashboard'))
    
    # Get attendance records
    attendance_records = get_event_attendance_data(event_id)
    
    # Process attendance data for statistics
    stats = {
        'total_attendees': 0,
        'unique_devices': set(),
        'location_data': [],
        'attendance_by_date': {}
    }
    
    for record_key, attendees in attendance_records.items():
        date = record_key.split('_')[-1]
        stats['attendance_by_date'][date] = len(attendees)
        
        for attendee_id, attendee_info in attendees.items():
            stats['total_attendees'] += 1
            
            # Track unique devices
            if 'device_info' in attendee_info:
                device_info = attendee_info['device_info']
                # Handle different device_info formats
                if isinstance(device_info, dict):
                    device_id = device_info.get('device_id') or device_info.get('fingerprint')
                    # If device_id is still a dict, try to create a unique string
                    if isinstance(device_id, dict):
                        device_id = str(sorted(device_id.items()))
                    elif device_id:
                        device_id = str(device_id)
                else:
                    device_id = str(device_info)
                
                if device_id:
                    stats['unique_devices'].add(device_id)
            
            # Collect location data
            if 'location_info' in attendee_info:
                location = attendee_info['location_info']
                stats['location_data'].append({
                    'attendee_name': attendee_info.get('attendee_name', 'Unknown'),
                    'lat': location.get('latitude'),
                    'lng': location.get('longitude'),
                    'accuracy': location.get('accuracy'),
                    'marked_at': attendee_info.get('marked_at')
                })
    
    stats['unique_device_count'] = len(stats['unique_devices'])
    
    return render_template('event_attendance_stats.html', 
                         event=event_data, 
                         stats=stats)

@app.route('/api/events/<event_id>/settings', methods=['POST'])
@organizer_login_required
def update_event_settings(event_id):
    """Update event settings (status, registration status)"""
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        if not event_data or event_data.get('organizer_id') != organizer_username:
            return jsonify({'success': False, 'message': 'Event not found or access denied'}), 403
        
        # Get form data
        status = request.form.get('status')
        registration_status = request.form.get('registration_status')
        
        # Validate input
        valid_statuses = ['active', 'inactive', 'cancelled']
        valid_reg_statuses = ['open', 'closed']
        
        if status not in valid_statuses:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400
        
        if registration_status not in valid_reg_statuses:
            return jsonify({'success': False, 'message': 'Invalid registration status'}), 400
        
        # Update event in Firebase
        try:
            event_ref = firebase_db.ref.child('events').child(event_id)
            
            # Update the event data
            updates = {
                'status': status,
                'registration_status': registration_status,
                'last_updated': datetime.now().isoformat(),
                'updated_by': organizer_username
            }
            
            event_ref.update(updates)
            
            return jsonify({
                'success': True, 
                'message': 'Settings updated successfully',
                'updated_fields': updates
            })
            
        except Exception as e:
            print(f"Firebase update error: {e}")
            return jsonify({'success': False, 'message': 'Database update failed'}), 500
            
    except Exception as e:
        print(f"Error updating event settings: {e}")
        return jsonify({'success': False, 'message': 'Server error occurred'}), 500

@app.route('/api/attendance/stats/<event_id>')
@organizer_login_required
def get_attendance_stats_api(event_id):
    """API endpoint to get attendance statistics for an event"""
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        if not event_data or event_data.get('organizer_id') != organizer_username:
            return jsonify({'success': False, 'message': 'Event not found or access denied'}), 403
        
        # Get attendance data
        attendance_records = get_event_attendance_data(event_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        stats = {
            'total_registered': len(get_event_attendees_by_event(event_id) or {}),
            'total_attendance_today': 0,
            'unique_attendees': set(),
            'attendance_by_date': {}
        }
        
        # Process attendance records
        for record_key, record_data in attendance_records.items():
            if isinstance(record_data, dict):
                for attendee_id, attendee_info in record_data.items():
                    if isinstance(attendee_info, dict):
                        stats['unique_attendees'].add(attendee_id)
                        
                        # Count today's attendance
                        if record_key.endswith(today):
                            stats['total_attendance_today'] += 1
        
        stats['unique_attendees_count'] = len(stats['unique_attendees'])
        
        return jsonify({
            'success': True,
            'stats': {
                'total_registered': stats['total_registered'],
                'attendance_today': stats['total_attendance_today'],
                'unique_attendees': stats['unique_attendees_count']
            }
        })
        
    except Exception as e:
        print(f"Error getting attendance stats: {e}")
        return jsonify({'success': False, 'message': 'Failed to get stats'}), 500

@app.route('/api/attendance/count/<event_id>')
def get_attendance_count_api(event_id):
    """API endpoint to get attendance count for a specific date"""
    try:
        # Get date from query parameter, default to today
        date_filter = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
        
        # Get attendance data for the event
        attendance_records = get_event_attendance_data(event_id)
        
        count = 0
        recent_attendees = []
        
        # Count attendance for the specific date
        for record_key, attendees_dict in attendance_records.items():
            if record_key.endswith(date_filter) and isinstance(attendees_dict, dict):
                count += len(attendees_dict)
                
                # Get recent attendees for this date
                for attendee_id, attendee_info in attendees_dict.items():
                    if isinstance(attendee_info, dict):
                        recent_attendees.append({
                            'name': attendee_info.get('attendee_name', attendee_info.get('name', 'Unknown')),
                            'time': attendee_info.get('marked_at', attendee_info.get('timestamp', '')),
                            'enrollment_no': attendee_info.get('enrollment_no', attendee_id)
                        })
        
        # Sort recent attendees by time (most recent first)
        recent_attendees.sort(key=lambda x: x.get('time', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'count': count,
            'date': date_filter,
            'recent': recent_attendees[:5]  # Return last 5 attendees
        })
        
    except Exception as e:
        print(f"Error getting attendance count: {e}")
        return jsonify({'success': False, 'message': 'Failed to get attendance count'}), 500

@app.route('/debug/attendance/<event_id>')
@organizer_login_required
def debug_attendance_data(event_id):
    """Debug endpoint to see raw attendance data structure"""
    try:
        attendance_data = get_event_attendance_data(event_id)
        return jsonify({
            'success': True,
            'raw_data': attendance_data,
            'data_type': str(type(attendance_data)),
            'keys': list(attendance_data.keys()) if isinstance(attendance_data, dict) else 'Not a dict'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/events/<event_id>/edit', methods=['POST'])
@organizer_login_required
def edit_event_api(event_id):
    """API endpoint to edit event details"""
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        # Check if event exists and user has permission
        if not event_data:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
            
        if event_data.get('organizer_id') != organizer_username:
            return jsonify({'success': False, 'message': 'Unauthorized to edit this event'}), 403
        
        # Get the updated data from request
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['event_name', 'event_date', 'event_time', 'location']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field.replace("_", " ").title()} is required'}), 400
        
        # Prepare updated event data (preserving existing geofencing settings)
        updated_event = {
            'event_id': event_id,
            'organizer_id': organizer_username,
            'event_name': data['event_name'].strip(),
            'event_description': data.get('description', '').strip(),
            'event_date': data['event_date'],
            'event_time': data['event_time'],
            'event_location': data['location'].strip(),
            'capacity': data.get('max_attendees'),
            'registration_open': data.get('registration_open', True),
            'latitude': event_data.get('latitude'),  # Preserve existing geofencing settings
            'longitude': event_data.get('longitude'),  # Preserve existing geofencing settings
            'geofence_radius': event_data.get('geofence_radius') or event_data.get('attendance_radius'),  # Support both field names for compatibility
            'one_attendance_per_device': event_data.get('one_attendance_per_device', False),  # Preserve existing setting
            'created_at': event_data.get('created_at'),  # Preserve original creation time
            'updated_at': datetime.now().isoformat()
        }
        
        # Save the updated event
        success = firebase_db.save_event(event_id, updated_event)
        if success:
            return jsonify({
                'success': True, 
                'message': 'Event details updated successfully',
                'event': updated_event
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to update event details'}), 500
            
    except Exception as e:
        print(f"Error editing event {event_id}: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while updating the event'}), 500

@app.route('/api/events/<event_id>', methods=['DELETE'])
@organizer_login_required
def delete_event_api(event_id):
    """API endpoint to delete an event and all associated data"""
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        # Check if event exists and user has permission
        if not event_data:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
            
        if event_data.get('organizer_id') != organizer_username:
            return jsonify({'success': False, 'message': 'You do not have permission to delete this event'}), 403
        
        # Delete the event and all associated data
        success = delete_event(event_id)
        
        if success:
            return jsonify({
                'success': True, 
                'message': 'Event deleted successfully',
                'deleted_event_id': event_id
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to delete event from database'}), 500
            
    except Exception as e:
        print(f"Error in delete event API: {e}")
        return jsonify({'success': False, 'message': 'Server error occurred during deletion'}), 500

@app.route('/api/auto_logout', methods=['POST'])
def auto_logout():
    """Handle automatic logout when page is closed"""
    try:
        session.clear()
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        print(f"Error during auto logout: {e}")
        return jsonify({'success': False, 'message': 'Logout failed'}), 500

@app.route('/admin/events')
@admin_login_required
def admin_view_events():
    """Admin view of all events"""
    try:
        events = get_all_events()
        organizers = get_all_event_organizers()
        
        # Process events with additional info
        events_list = []
        for event_id, event_data in events.items():
            # Get attendee count
            attendees = get_event_attendees_by_event(event_id)
            attendee_count = len(attendees) if attendees else 0
            
            # Get organizer name
            organizer_id = event_data.get('organizer_id', '')
            organizer_info = organizers.get(organizer_id, {})
            organizer_name = organizer_info.get('organizer_name', 'Unknown')
            
            event_info = {
                'event_id': event_id,
                'event_name': event_data.get('event_name', 'Untitled Event'),
                'organizer_name': organizer_name,
                'organizer_id': organizer_id,
                'event_date': event_data.get('event_date', 'TBD'),
                'event_time': event_data.get('event_time', 'TBD'),
                'event_location': event_data.get('event_location', 'TBD'),
                'capacity': event_data.get('capacity', 'Unlimited'),
                'attendee_count': attendee_count,
                'status': 'active',  # Always show as active for simplicity
                'registration_status': 'open' if event_data.get('registration_open', True) else 'closed',
                'created_at': event_data.get('created_at', datetime.now().isoformat()),
                'geofencing_enabled': event_data.get('geofencing_enabled', False)
            }
            events_list.append(event_info)
        
        # Sort by creation date (newest first)
        events_list.sort(key=lambda x: x['created_at'], reverse=True)
        
        return render_template('admin/events.html', events=events_list)
        
    except Exception as e:
        print(f"Error in admin events view: {e}")
        flash('Error loading events', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/reports')
@admin_login_required
def admin_reports():
    """Admin reports and analytics"""
    try:
        events = get_all_events()
        organizers = get_all_event_organizers()
        
        # Calculate statistics
        total_events = len(events)
        total_organizers = len(organizers)
        active_events = sum(1 for event in events.values() if event.get('status') == 'active')
        
        # Calculate total attendees across all events
        total_attendees = 0
        events_with_geofencing = 0
        
        for event_id, event_data in events.items():
            attendees = get_event_attendees_by_event(event_id)
            total_attendees += len(attendees) if attendees else 0
            
            if event_data.get('geofencing_enabled'):
                events_with_geofencing += 1
        
        stats = {
            'total_events': total_events,
            'active_events': active_events,
            'total_organizers': total_organizers,
            'total_attendees': total_attendees,
            'events_with_geofencing': events_with_geofencing,
            'geofencing_percentage': round((events_with_geofencing / total_events * 100) if total_events > 0 else 0, 1)
        }
        
        return render_template('admin/reports.html', stats=stats, events=events, organizers=organizers)
        
    except Exception as e:
        print(f"Error generating admin reports: {e}")
        flash('Error generating reports', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/api/events/<event_id>/time-slots', methods=['GET', 'POST'])
@organizer_login_required
def manage_time_slots(event_id):
    """Manage time slots for an event"""
    try:
        organizer_username = session.get('organizer_username')
        event_data = get_event(event_id)
        
        if not event_data or event_data.get('organizer_id') != organizer_username:
            return jsonify({'success': False, 'message': 'Event not found or access denied'}), 403
        
        if request.method == 'GET':
            # Get existing time slots
            slots = firebase_db.get_event_time_slots(event_id)
            return jsonify({'success': True, 'slots': slots})
        
        elif request.method == 'POST':
            # Save time slots
            data = request.get_json()
            slots = data.get('slots', [])
            
            # Validate slots
            for slot in slots:
                if not all(k in slot for k in ['class_type', 'start_time', 'end_time']):
                    return jsonify({'success': False, 'message': 'Invalid slot data'}), 400
            
            success = firebase_db.save_event_time_slots(event_id, slots)
            if success:
                return jsonify({'success': True, 'message': 'Time slots saved successfully'})
            else:
                return jsonify({'success': False, 'message': 'Failed to save time slots'}), 500
                
    except Exception as e:
        print(f"Error managing time slots: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

# Attendance View Routes
@app.route('/admin/attendance/view')
@admin_login_required
def admin_attendance_view():
    """Admin view for attendance records - using the enhanced attendance_view.html"""
    try:
        # Mock data for demonstration - replace with actual data from your database
        sample_attendance = [
            {
                'enrollment': 'A123456789',
                'name': 'John Doe',
                'attendance': ['P', 'A', 'P', 'P', 'A']
            },
            {
                'enrollment': 'A987654321', 
                'name': 'Jane Smith',
                'attendance': ['P', 'P', 'A', 'P', 'P']
            },
            {
                'enrollment': 'A456789123',
                'name': 'Mike Johnson', 
                'attendance': ['A', 'P', 'P', 'A', 'P']
            },
            {
                'enrollment': 'A789123456',
                'name': 'Sarah Wilson',
                'attendance': ['P', 'P', 'P', 'P', 'P']
            }
        ]
        
        sample_dates = ['2024-11-01', '2024-11-02', '2024-11-03', '2024-11-04', '2024-11-05']
        
        return render_template('attendance_view.html',
                             attendance=sample_attendance,
                             dates=sample_dates,
                             subject_name='Computer Science',
                             subject_code='CS101')
                             
    except Exception as e:
        print(f"Error in attendance view: {e}")
        flash('Error loading attendance records', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/attendance/export')
@admin_login_required
def export_csv():
    """Export attendance to CSV"""
    # Mock implementation - replace with actual CSV export logic
    flash('CSV export functionality to be implemented', 'info')
    return redirect(url_for('admin_attendance_view'))

@app.route('/admin/attendance/clear', methods=['POST'])
@admin_login_required
def clear_attendance():
    """Clear all attendance data"""
    # Mock implementation - replace with actual clear logic
    flash('Clear attendance functionality to be implemented', 'info')
    return redirect(url_for('admin_attendance_view'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Different port to avoid conflicts