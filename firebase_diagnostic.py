#!/usr/bin/env python3
"""
Firebase Message Data Diagnostic Tool
Run this to see what's actually stored in Firebase
"""

import firebase_admin
from firebase_admin import credentials, firestore
import json
from datetime import datetime
import os

print("=" * 80)
print("FIREBASE MESSAGES DIAGNOSTIC TOOL")
print("=" * 80)

# Find firebase config
config_paths = [
    'firebase_config.json',
    'config/firebase_config.json',
    '../firebase_config.json'
]

firebase_config = None
for path in config_paths:
    if os.path.exists(path):
        print(f"✅ Found config at: {path}")
        with open(path, 'r', encoding='utf-8-sig') as f:
            firebase_config = json.load(f)
        break

if not firebase_config:
    print("\n❌ Cannot find firebase-config.json")
    print("Please make sure it's in one of these locations:")
    for path in config_paths:
        print(f"  - {path}")
    exit(1)

# Initialize Firebase
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized successfully")
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    exit(1)

db = firestore.client()

# Get all messages
print("\n" + "=" * 80)
print("FETCHING ALL MESSAGES...")
print("=" * 80)

try:
    messages_ref = db.collection('messages').stream()
    messages_found = 0
    
    for doc in messages_ref:
        messages_found += 1
        message_data = doc.to_dict()
        
        print(f"\n{'='*80}")
        print(f"MESSAGE #{messages_found}")
        print(f"Document ID: {doc.id}")
        print(f"{'='*80}")
        
        # Show all fields
        print("\n📋 All fields in this document:")
        for key, value in message_data.items():
            value_type = type(value).__name__
            
            # Handle different value types
            if value is None:
                display_value = "❌ NULL/None (PROBLEM!)"
                status = "❌"
            elif isinstance(value, str) and value == "None":
                display_value = "❌ STRING 'None' (PROBLEM!)"
                status = "❌"
            elif isinstance(value, str) and not value.strip():
                display_value = "⚠️  EMPTY STRING"
                status = "⚠️"
            elif isinstance(value, str):
                display_value = f'"{value}"'
                status = "✅"
            elif isinstance(value, (int, float, bool)):
                display_value = str(value)
                status = "✅"
            else:
                display_value = str(value)[:100]
                status = "✅"
            
            print(f"  {status} {key:20s} = {display_value} ({value_type})")
        
        # Check for the critical fields
        print("\n🔍 Critical Field Check:")
        critical_fields = {
            'sender_name': 'Sender Name',
            'sender_email': 'Sender Email',
            'subject': 'Subject',
            'message': 'Message Content',
            'contractor_id': 'Contractor ID',
            'type': 'Message Type'
        }
        
        all_ok = True
        for field, label in critical_fields.items():
            if field not in message_data:
                print(f"  ❌ MISSING: {label} (field '{field}' not found)")
                all_ok = False
            elif message_data[field] is None:
                print(f"  ❌ NULL: {label} = None")
                all_ok = False
            elif isinstance(message_data[field], str) and message_data[field] == "None":
                print(f"  ❌ BAD VALUE: {label} = 'None' (string)")
                all_ok = False
            elif isinstance(message_data[field], str) and not message_data[field].strip():
                print(f"  ⚠️  EMPTY: {label} = '' (empty string)")
                all_ok = False
            else:
                value_preview = message_data[field]
                if isinstance(value_preview, str) and len(value_preview) > 50:
                    value_preview = value_preview[:50] + "..."
                print(f"  ✅ OK: {label} = {repr(value_preview)}")
        
        if not all_ok:
            print("\n🚨 THIS MESSAGE HAS PROBLEMS! ^^^ See above ^^^")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: Found {messages_found} total messages")
    print(f"{'='*80}")
    
    if messages_found == 0:
        print("\n⚠️  NO MESSAGES FOUND IN FIREBASE!")
        print("\nPossible reasons:")
        print("  1. No messages have been sent yet")
        print("  2. Messages are in a different collection name")
        print("  3. Try sending a test message from user to contractor")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS:")
    print("=" * 80)
    
    if messages_found > 0:
        print("\nIf you see ❌ or ⚠️  above:")
        print("  → Problem: Messages are being CREATED with None/empty values")
        print("  → Fix: Check user_routes.py and contractor_profile.html form")
        print("\nIf all fields show ✅ OK:")
        print("  → Problem: Display code issue (unlikely given your current code)")
    
    print("=" * 80)

except Exception as e:
    print(f"\n❌ Error accessing Firebase: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")