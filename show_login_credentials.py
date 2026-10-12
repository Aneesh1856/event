#!/usr/bin/env python3
"""
Event Attendance System - Login Credentials Setup
This script helps you set up initial login credentials for your event system
"""

import sys
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

def create_sample_organizer():
    """Create sample organizer data"""
    return {
        'organizer_name': 'John Doe',
        'organizer_email': 'john.doe@example.com',
        'organizer_phone': '+1234567890',
        'password': generate_password_hash('organizer123'),  # Default password
        'created_at': datetime.now().isoformat(),
        'is_active': True,
        'events_created': 0
    }

def display_login_info():
    """Display login information for the system"""
    
    print("🔐 EVENT ATTENDANCE SYSTEM - LOGIN CREDENTIALS")
    print("=" * 60)
    print()
    
    print("📋 AVAILABLE LOGIN TYPES:")
    print("-" * 30)
    print("1. ADMIN LOGIN")
    print("2. EVENT ORGANIZER LOGIN")
    print()
    
    print("🔑 DEFAULT CREDENTIALS:")
    print("-" * 30)
    
    print("1. ADMIN ACCOUNT:")
    print("   Username: admin")
    print("   Password: admin@123")
    print("   Purpose: System administration, manage organizers")
    print()
    
    print("2. SAMPLE EVENT ORGANIZER:")
    print("   Username: john.doe")
    print("   Password: organizer123") 
    print("   Purpose: Create and manage events")
    print()
    
    print("🚀 HOW TO LOGIN:")
    print("-" * 30)
    print("1. Run your Flask app: python event_app.py")
    print("2. Go to: http://localhost:5000")
    print("3. Choose login type (Admin or Organizer)")
    print("4. Enter credentials above")
    print()
    
    print("⚙️  TO CREATE NEW ORGANIZERS:")
    print("-" * 30)
    print("1. Login as admin")
    print("2. Go to admin dashboard") 
    print("3. Add new organizers")
    print("OR")
    print("1. Use the create_organizer.py script")
    print()
    
    print("🔧 FIRST-TIME SETUP:")
    print("-" * 30)
    print("1. Make sure Firebase is connected")
    print("2. Run: python test_firebase_connection.py")
    print("3. If successful, run: python setup_initial_data.py")
    print("4. Start the app: python event_app.py")

def create_setup_script():
    """Create a script to set up initial data"""
    
    setup_script = '''#!/usr/bin/env python3
"""
Initial Data Setup Script
Run this after connecting to Firebase to create initial login accounts
"""

import sys
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_initial_data():
    """Set up initial admin and sample organizer accounts"""
    
    print("🚀 Setting up initial data...")
    
    try:
        from firebase_config import firebase_db
        
        if firebase_db.ref is None:
            print("❌ Firebase not connected! Run test_firebase_connection.py first")
            return False
        
        # 1. Setup Admin Account
        print("1. Setting up admin account...")
        admin_data = {
            'credentials': {
                'username': 'admin',
                'password': generate_password_hash('admin@123')
            },
            'created_at': datetime.now().isoformat()
        }
        
        if firebase_db.save_admin_data(admin_data):
            print("✅ Admin account created!")
            print("   Username: admin")
            print("   Password: admin@123")
        else:
            print("❌ Failed to create admin account")
        
        # 2. Setup Sample Organizer
        print("\\n2. Setting up sample organizer...")
        organizer_data = {
            'organizer_name': 'John Doe',
            'organizer_email': 'john.doe@example.com',
            'organizer_phone': '+1234567890',
            'password': generate_password_hash('organizer123'),
            'created_at': datetime.now().isoformat(),
            'is_active': True,
            'events_created': 0
        }
        
        if firebase_db.save_event_organizer('john.doe', organizer_data):
            print("✅ Sample organizer created!")
            print("   Username: john.doe")
            print("   Password: organizer123")
            print("   Name: John Doe")
        else:
            print("❌ Failed to create sample organizer")
        
        # 3. Create Sample Event (optional)
        print("\\n3. Creating sample event...")
        sample_event = {
            'event_id': 'SAMPLE001',
            'event_name': 'Tech Meetup 2024',
            'event_description': 'A sample tech meetup event',
            'event_date': '2024-12-15',
            'event_time': '18:00',
            'event_location': 'Conference Room A, Tech Hub',
            'organizer_id': 'john.doe',
            'organizer_name': 'John Doe',
            'max_attendees': 50,
            'registration_open': True,
            'created_at': datetime.now().isoformat(),
            'status': 'scheduled'
        }
        
        if firebase_db.save_event('SAMPLE001', sample_event):
            print("✅ Sample event created!")
            print("   Event: Tech Meetup 2024")
            print("   Date: December 15, 2024")
        else:
            print("❌ Failed to create sample event")
        
        print("\\n🎉 Initial setup complete!")
        print("\\n🔗 Next steps:")
        print("1. Run: python event_app.py")
        print("2. Go to: http://localhost:5000")
        print("3. Login with the credentials above")
        
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False

if __name__ == "__main__":
    setup_initial_data()
    input("\\nPress Enter to exit...")
'''
    
    with open("setup_initial_data.py", "w") as f:
        f.write(setup_script)
    
    print("✅ Created setup_initial_data.py script")

def create_organizer_script():
    """Create a script to add new organizers"""
    
    organizer_script = '''#!/usr/bin/env python3
"""
Create New Event Organizer
Use this script to add new organizers to your system
"""

import sys
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_organizer():
    """Interactive script to create a new organizer"""
    
    print("👤 CREATE NEW EVENT ORGANIZER")
    print("=" * 40)
    
    try:
        from firebase_config import firebase_db
        
        if firebase_db.ref is None:
            print("❌ Firebase not connected! Please check your connection first.")
            return False
        
        # Get organizer details
        print("\\nEnter organizer details:")
        username = input("Username (login ID): ").lower().strip()
        name = input("Full Name: ").strip()
        email = input("Email: ").strip()
        phone = input("Phone: ").strip()
        password = input("Password: ").strip()
        
        if not all([username, name, email, phone, password]):
            print("❌ All fields are required!")
            return False
        
        # Check if username already exists
        existing = firebase_db.get_event_organizer(username)
        if existing:
            print(f"❌ Username '{username}' already exists!")
            return False
        
        # Create organizer data
        organizer_data = {
            'organizer_name': name,
            'organizer_email': email,
            'organizer_phone': phone,
            'password': generate_password_hash(password),
            'created_at': datetime.now().isoformat(),
            'is_active': True,
            'events_created': 0
        }
        
        # Save to Firebase
        if firebase_db.save_event_organizer(username, organizer_data):
            print("\\n✅ Organizer created successfully!")
            print(f"   Username: {username}")
            print(f"   Name: {name}")
            print(f"   Email: {email}")
            print("\\n🔗 They can now login at: http://localhost:5000")
        else:
            print("❌ Failed to create organizer!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    create_organizer()
    input("\\nPress Enter to exit...")
'''
    
    with open("create_organizer.py", "w") as f:
        f.write(organizer_script)
    
    print("✅ Created create_organizer.py script")

if __name__ == "__main__":
    print("🎯 EVENT ATTENDANCE SYSTEM SETUP")
    print()
    
    # Display login information
    display_login_info()
    
    print("📝 CREATING HELPER SCRIPTS:")
    print("-" * 30)
    
    # Create helper scripts
    create_setup_script()
    create_organizer_script()
    
    print()
    print("🎉 Setup complete! Helper scripts created:")
    print("   - setup_initial_data.py (run this first)")
    print("   - create_organizer.py (use this to add new organizers)")
    print()
    print("📋 QUICK START:")
    print("1. Connect to Firebase database")
    print("2. Run: python setup_initial_data.py")
    print("3. Run: python event_app.py")
    print("4. Login with credentials above")
    
    input("\nPress Enter to exit...")