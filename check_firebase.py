import os
import json

print("=" * 60)
print("🔍 FIREBASE CONFIGURATION DIAGNOSTIC")
print("=" * 60)

# Check if file exists
config_file = 'firebase_config.json'
print(f"\n1. Checking if {config_file} exists...")
if os.path.exists(config_file):
    print(f"   ✅ File exists at: {os.path.abspath(config_file)}")
else:
    print(f"   ❌ File NOT found!")
    print(f"   Expected location: {os.path.abspath(config_file)}")
    exit(1)

# Check file size
file_size = os.path.getsize(config_file)
print(f"\n2. File size: {file_size} bytes")
if file_size < 100:
    print("   ⚠️  Warning: File seems too small!")

# Check file encoding
print(f"\n3. Checking file encoding...")
with open(config_file, 'rb') as f:
    first_bytes = f.read(3)
    if first_bytes == b'\xef\xbb\xbf':
        print("   ⚠️  UTF-8 BOM detected! This needs to be removed.")
    else:
        print("   ✅ No BOM detected")

# Try to parse JSON
print(f"\n4. Attempting to parse JSON...")
try:
    with open(config_file, 'r', encoding='utf-8-sig') as f:
        config_data = json.load(f)
    print("   ✅ JSON is valid!")
    
    # Check required fields
    print(f"\n5. Checking required Firebase fields...")
    required_fields = [
        'type', 'project_id', 'private_key_id', 
        'private_key', 'client_email', 'client_id'
    ]
    
    missing_fields = []
    for field in required_fields:
        if field in config_data:
            print(f"   ✅ {field}: Present")
        else:
            print(f"   ❌ {field}: MISSING")
            missing_fields.append(field)
    
    if missing_fields:
        print(f"\n   ⚠️  Missing fields: {', '.join(missing_fields)}")
    else:
        print(f"\n   ✅ All required fields present!")
    
    # Show project info
    print(f"\n6. Firebase Project Info:")
    print(f"   Project ID: {config_data.get('project_id', 'N/A')}")
    print(f"   Client Email: {config_data.get('client_email', 'N/A')}")
    
except json.JSONDecodeError as e:
    print(f"   ❌ JSON parsing error: {e}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)