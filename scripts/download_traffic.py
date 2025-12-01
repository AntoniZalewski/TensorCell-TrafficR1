import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from huggingface_hub import snapshot_download
import os

# Create the directory
os.makedirs('/app/models/Traffic-R1', exist_ok=True)

# Download the model
print("Starting download of Season998/Traffic-R1...")
snapshot_download(repo_id='Season998/Traffic-R1', local_dir='/app/models/Traffic-R1')
print("Download complete!")
