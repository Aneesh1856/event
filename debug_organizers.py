#!/usr/bin/env python3
"""
Debug script to check organizer data structure in Firebase
"""

from firebase_config import get_all_event_organizers

def main():
    print("=== Debugging Organizer Data ===")
    
    try:
        organizers = get_all_event_organizers()
        
        if not organizers:
            print("❌ No organizers found in database")
            return
        
        print(f"✅ Found {len(organizers)} organizers")
        print()
        
        for org_id, org_data in organizers.items():
            print(f"Organizer ID: {org_id}")
            print(f"Data Type: {type(org_data)}")
            
            if org_data:
                print("Available fields:")
                for key, value in org_data.items():
                    print(f"  - {key}: {value}")
                
                # Test the field resolution logic
                name = (org_data.get('organizer_name') or 
                       org_data.get('name') or 
                       org_data.get('full_name') or 
                       'Unknown')
                
                email = (org_data.get('organizer_email') or 
                        org_data.get('email') or 
                        'Unknown')
                
                phone = (org_data.get('organizer_phone') or 
                        org_data.get('phone') or 
                        'Unknown')
                
                print("Field Resolution Results:")
                print(f"  - Name: {name}")
                print(f"  - Email: {email}")
                print(f"  - Phone: {phone}")
            else:
                print("❌ No data found for this organizer")
            
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()