#!/usr/bin/env python3
"""
Utility script to fix existing event registrations that are missing enrollment numbers.
This script will add enrollment numbers to existing registrations by matching WhatsApp numbers 
with the student database.
"""

from firebase_config import firebase_db
import json

def fix_existing_registrations():
    """Fix existing registrations by adding missing enrollment numbers"""
    print("🔧 Starting fix for existing event registrations...")
    
    try:
        # Get all events
        all_events = firebase_db.get_all_events()
        if not all_events:
            print("❌ No events found.")
            return
        
        print(f"📋 Found {len(all_events)} events to check.")
        
        fixed_count = 0
        
        for event_id, event_data in all_events.items():
            print(f"\n🎯 Checking event: {event_data.get('event_name', event_id)}")
            
            # Get registrations for this event
            registrations_ref = firebase_db.ref.child('event_registrations').child(event_id)
            registrations = registrations_ref.get() or {}
            
            if not registrations:
                print("   ℹ️  No registrations found for this event.")
                continue
                
            print(f"   📝 Found {len(registrations)} registrations to check.")
            
            for attendee_id, registration_data in registrations.items():
                # Check if enrollment_no is missing
                if not registration_data.get('enrollment_no'):
                    whatsapp_number = registration_data.get('whatsapp_number', '')
                    attendee_name = registration_data.get('attendee_name', '')
                    
                    print(f"   🔍 Missing enrollment for: {attendee_name} ({whatsapp_number})")
                    
                    if whatsapp_number:
                        # Try to find student by phone number
                        all_students = firebase_db.get_all_students()
                        found_student = None
                        
                        for enrollment_no, student_data in (all_students or {}).items():
                            if student_data.get('phone', '').strip() == whatsapp_number.strip():
                                found_student = student_data
                                found_student['enrollment_no'] = enrollment_no
                                break
                        
                        if found_student:
                            # Update the registration with enrollment number and other details
                            updated_registration = {
                                **registration_data,
                                'enrollment_no': found_student['enrollment_no'],
                                'school': found_student.get('school', ''),
                                'branch': found_student.get('branch', ''),
                                'semester': found_student.get('semester', '')
                            }
                            
                            # Save the updated registration
                            registrations_ref.child(attendee_id).set(updated_registration)
                            
                            print(f"   ✅ Fixed: {attendee_name} → Enrollment: {found_student['enrollment_no']}")
                            fixed_count += 1
                        else:
                            print(f"   ⚠️  No matching student found in database for: {attendee_name}")
                    else:
                        print(f"   ⚠️  No WhatsApp number available for: {attendee_name}")
        
        print(f"\n🎉 Fix completed! Updated {fixed_count} registrations.")
        print("💡 Now new registrations will automatically include enrollment numbers.")
        
    except Exception as e:
        print(f"❌ Error during fix: {e}")

if __name__ == "__main__":
    fix_existing_registrations()