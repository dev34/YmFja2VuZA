import hashlib
import requests
import subprocess
import os
import os
from github import Github



# Function to compute file hash
def compute_file_hash(file_path, hash_algorithm="sha256"):
    hash_func = hashlib.new(hash_algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hash_func.update(chunk)
    return hash_func.hexdigest()

# Step 1: Download the file
url = "https://fastschedule.github.io/db/timetable.json"
old_file = "timetable.old.json"
new_file = "timetable.json"

try:
    response = requests.get(url)
    response.raise_for_status()
    with open(old_file, "wb") as f:
        f.write(response.content)
    print(f"Downloaded and saved as {old_file}")
except Exception as e:
    print(f"Error downloading the file: {e}")
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
    print("The hashes are identical. The files are the same.")
else:
    print("The hashes are different. The files have changed.")
    print("Uploading the new file to Github...")

    GITHUB_TOKEN = os.getenv("TOKEN")
    REPO_NAME = "fastschedule/fastschedule.github.io"
    FILE_PATH = "db/timetable.json"
    LOCAL_FILE_PATH = "timetable.json"
    COMMIT_MESSAGE = "update timetable.json"

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    try:
        contents = repo.get_contents(FILE_PATH)
        with open(LOCAL_FILE_PATH, "r") as file:
            content = file.read()
        repo.update_file(contents.path, COMMIT_MESSAGE, content, contents.sha)
        print(f"File '{FILE_PATH}' updated successfully!")
    except Exception as e:
        if "404" in str(e):
            with open(LOCAL_FILE_PATH, "r") as file:
                content = file.read()
            repo.create_file(FILE_PATH, COMMIT_MESSAGE, content)
            print(f"File '{FILE_PATH}' created successfully!")
        else:
            print(f"An error occurred: {e}")
