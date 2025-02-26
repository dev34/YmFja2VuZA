import hashlib
import subprocess
import requests
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin SDK
cred = credentials.Certificate("firebase-key.json")  # Path to your Firebase private key JSON
firebase_admin.initialize_app(cred)
db = firestore.client()

# Function to compute file hash
def compute_file_hash(file_path, hash_algorithm="md5"):
    hash_func = hashlib.new(hash_algorithm)
    with open(file_path, "rb") as f:
        json_data = json.load(f)  # Load JSON to normalize
        normalized_json = json.dumps(json_data, sort_keys=True, separators=(',', ':'))  # Remove spaces
        hash_func.update(normalized_json.encode('utf-8'))  # Encode before hashing
    return hash_func.hexdigest()

# Step 1: Download the file from Firestore
old_file = "timetable.old.json"
new_file = "timetable.json"

try:
    #download .json file from "https://fastscheduledb.abdulmoiz-marz.workers.dev/" and add param to increment the view counter
    BASE_URL = "https://fastscheduledb.abdulmoiz-marz.workers.dev?nocount=true"

    headers = {
        "Origin": "https://fastschedule.github.io" 
    }
    response = requests.get(BASE_URL, headers=headers)
    #write json data to file
    response = response.json()
    response = response["data"]
    with open(old_file, "w") as f:
        json.dump(response, f, indent=4)
    print(f"Downloaded and saved as {old_file}")
except Exception as e:
    print(f"Error fetching from Firestore: {e}")
    exit(1)

# Step 2: Compute hash of the downloaded file
old_file_hash = compute_file_hash(old_file)
print(f"Hash of {old_file}: {old_file_hash}")

# Step 3: Run the script to generate new timetable.json
script_name = "v3_final.py"
try:
    subprocess.run(["python", script_name], check=True)
    print(f"Script {script_name} executed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Error running {script_name}: {e}")
    exit(1)

# Step 4: Compute hash of the newly generated file
if os.path.exists(new_file):
    new_file_hash = compute_file_hash(new_file)
    print(f"Hash of {new_file}: {new_file_hash}")
else:
    print(f"Error: {new_file} was not created.")
    exit(1)

# Step 5: Compare the hashes
if old_file_hash == new_file_hash:
    print("The hashes are identical. The files are the same. No need to upload.")
else:
    print("The hashes are different. Updating Firestore...")

    try:
        with open(new_file, "r") as file:
            json_data = json.load(file)
        db.collection("data").document("timetable").set({"json": json.dumps(json_data)})
        print("✅ Timetable successfully uploaded to Firestore!")
    except Exception as e:
        print(f"An error occurred while updating Firestore: {e}")
