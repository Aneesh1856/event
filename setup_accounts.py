#!/usr/bin/env python3
"""
Simple Initial Data Setup
Creates admin and sample organizer accounts
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_accounts():
    """Set up initial admin and sample organizer accounts"""
            
    print("Setting up initial accounts...")
    
    try:
        # Import after adding path
        from werkzeug.security import generate_password_hash
        from firebase_config import firebase_db
        
        if firebase_db.ref is None:
            print("ERROR: Firebase not connected!")
            print("Please update your database URL in firebase_config.py first")
            return False
        
        # 1. Setup Admin Account
        print("1. Creating admin account...")
        admin_data = {
            'credentials': {
                'username': 'admin',
                'password': generate_password_hash('admin@123')
            },
            'created_at': datetime.now().isoformat()
        }
        
        if firebase_db.save_admin_data(admin_data):
            print("   ADMIN CREATED!")
            print("   Username: admin")
            print("   Password: admin@123")
        else:
            print("   Failed to create admin")
        
        # 2. Setup Sample Organizer
        print("2. Creating sample organizer...")
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
            print("   ORGANIZER CREATED!")
            print("   Username: john.doe") 
            print("   Password: organizer123")
        else:
            print("   Failed to create organizer")
        
        print()
        print("SETUP COMPLETE!")
        print("You can now login at: http://localhost:5000")
        
        return True
        
    except Exception as e:
        print(f"Setup failed: {e}")
        print()
        print("Make sure to:")
        print("1. Update Firebase database URL")
        print("2. Install: pip install firebase-admin werkzeug")
        return False

if __name__ == "__main__":
    setup_accounts()
    input("\nPress Enter to exit...")