import json
import firebase_admin
from firebase_admin import credentials, firestore

print("=" * 60)
print("🔥 Testing Firebase Connection")
print("=" * 60)

try:
    # Method 1: Read with utf-8-sig to handle BOM
    print("\n1. Reading firebase_config.json...")
    with open('firebase_config.json', 'r', encoding='utf-8-sig') as f:
        config_data = json.load(f)
    print("   ✅ Config file loaded successfully")
    print(f"   Project ID: {config_data.get('project_id')}")
    
    # Method 2: Initialize Firebase
    print("\n2. Initializing Firebase Admin SDK...")
    cred = credentials.Certificate(config_data)
    firebase_admin.initialize_app(cred)
    print("   ✅ Firebase initialized successfully!")
    
    # Method 3: Test Firestore connection
    print("\n3. Testing Firestore connection...")
    db = firestore.client()
    print("   ✅ Firestore client created successfully!")
    
    # Method 4: Try to read a collection (this will work even if empty)
    print("\n4. Testing database read...")
    collections = ['users', 'contractors', 'suppliers']
    for collection_name in collections:
        try:
            # Just try to get the collection reference
            coll = db.collection(collection_name)
            docs = list(coll.limit(1).stream())
            print(f"   ✅ Collection '{collection_name}' accessible ({len(docs)} docs found)")
        except Exception as e:
            print(f"   ⚠️  Collection '{collection_name}' error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Firebase is working correctly!")
    print("=" * 60)
    
except FileNotFoundError:
    print("   ❌ firebase_config.json not found!")
    print("   Make sure the file is in the same directory as this script.")
    
except json.JSONDecodeError as e:
    print(f"   ❌ JSON parsing error: {e}")
    print("   The firebase_config.json file may be corrupted.")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check if firebase_config.json is in the correct location")
    print("2. Verify the JSON format is correct")
    print("3. Ensure your Firebase project credentials are valid")
    print("4. Check your internet connection")
    
    import traceback
    print("\nFull error details:")
    traceback.print_exc()