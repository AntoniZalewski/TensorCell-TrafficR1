import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from huggingface_hub import snapshot_download
import os
import shutil

# Target directory
target_dir = '/app/models/Traffic-R1-Fixed'

# Clean up if exists
if os.path.exists(target_dir):
    shutil.rmtree(target_dir)
os.makedirs(target_dir, exist_ok=True)

print(f"Downloading Traffic-R1 to {target_dir} (no symlinks)...")
snapshot_download(repo_id='Season998/Traffic-R1', 
                 local_dir=target_dir, 
                 local_dir_use_symlinks=False) # CRITICAL: Force real files
print("Download complete!")
