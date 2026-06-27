"""
GeoHeatAI — Download completed GeoTIFF exports from Google Cloud Storage.

Polls the geoheatai-exports GCS bucket, downloads completed .tif files to
data/raw/, and prints progress. Stops when file count stabilizes.
"""

import sys
import time
import subprocess
from pathlib import Path
from google.cloud import storage
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import DATA_RAW, GCS_BUCKET

EXPECTED_MIN_FILE_COUNT = 100  # Safety threshold before allowing stabilization exit

class ProgressFile:
    """Wrapper around a file-like object that updates a tqdm progress bar on write."""
    def __init__(self, file_obj, pbar):
        self.file_obj = file_obj
        self.pbar = pbar

    def write(self, data):
        self.file_obj.write(data)
        self.pbar.update(len(data))

    def flush(self):
        self.file_obj.flush()

def get_gcs_client() -> storage.Client:
    """Build and return storage Client using Application Default Credentials."""
    return storage.Client(project="geoheatai")

def list_export_blobs(client: storage.Client) -> list[storage.Blob]:
    """List all completed GeoTIFF blobs in the GCS bucket."""
    bucket = client.bucket(GCS_BUCKET)
    blobs = client.list_blobs(bucket)
    return [b for b in blobs if b.name.endswith(".tif")]

def download_blob(blob: storage.Blob, dest_dir: Path) -> bool:
    """
    Download a single GCS blob to dest_dir.
    Skips download if local file exists with identical size.
    Returns True if a new file was downloaded.
    """
    dest_path = dest_dir / blob.name
    
    # Check if local file exists and is of matching size (resume support)
    if dest_path.exists():
        local_size = dest_path.stat().st_size
        if local_size == blob.size:
            return False  # Already up to date
            
    # Stream download with a tqdm progress bar
    tmp_path = dest_path.with_suffix(".tif.part")
    
    # pacify chunk size to 5MB
    blob.chunk_size = 5 * 1024 * 1024
    
    with open(tmp_path, "wb") as f:
        with tqdm(
            total=blob.size,
            unit="B",
            unit_scale=True,
            desc=blob.name[:50],
            leave=True
        ) as pbar:
            progress_wrapper = ProgressFile(f, pbar)
            blob.download_to_file(progress_wrapper)
            
    tmp_path.rename(dest_path)
    return True

def download_all(client: storage.Client, dest_dir: Path = DATA_RAW) -> int:
    """Downloads all completed GeoTIFFs, returns count of newly downloaded files."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    blobs = list_export_blobs(client)
    total_blobs = len(blobs)
    print(f"[{time.strftime('%H:%M:%S')}] Found {total_blobs} files in GCS bucket '{GCS_BUCKET}'")
    
    newly_downloaded = 0
    for idx, blob in enumerate(blobs):
        print(f"  [{idx+1}/{total_blobs}] checking: {blob.name} ({blob.size / (1024*1024):.1f} MB)...")
        if download_blob(blob, dest_dir):
            newly_downloaded += 1
            print(f"    Downloaded successfully.")
            
    return newly_downloaded

def poll_and_download(interval_minutes: int = 5) -> None:
    """Poll GCS every interval_minutes. Stop when file count is stable."""
    client = get_gcs_client()
    prev_count = -1
    stable_polls = 0
    
    print(f"Starting GCS download poller for bucket: {GCS_BUCKET}")
    print(f"Polling interval: {interval_minutes} minutes")
    print(f"Downloading to:   {DATA_RAW}\n")
    
    while True:
        blobs = list_export_blobs(client)
        current_count = len(blobs)
        
        print(f"\n{'='*60}")
        print(f"  {current_count} files currently available in GCS")
        
        new_downloads = download_all(client, DATA_RAW)
        
        local_tifs = list(DATA_RAW.glob("geoheatai_*.tif"))
        print(f"  {len(local_tifs)} files downloaded locally")
        if new_downloads > 0:
            print(f"  ({new_downloads} new files added this poll)")

        # Stability checks
        if current_count == prev_count and current_count >= EXPECTED_MIN_FILE_COUNT:
            stable_polls += 1
        else:
            stable_polls = 0
            
        prev_count = current_count
        
        if stable_polls >= 2:
            print(f"\n✓ File count stable at {current_count} for {stable_polls} consecutive polls.")
            print(f"All exports complete. Run:")
            print("  python src/utils/pipeline_runner.py")
            break
            
        print(f"\n  Waiting {interval_minutes} minutes before next poll...")
        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    print("GeoHeatAI — GCS Export Downloader\n")
    
    # Check if gcloud CLI is available
    try:
        res = subprocess.run(["gcloud", "version"], capture_output=True, text=True)
        gcloud_installed = (res.returncode == 0)
    except Exception:
        gcloud_installed = False
        
    if not gcloud_installed:
        print("ERROR: gcloud CLI not found in PATH.")
        print("\nRun these setup commands first:")
        print(" 1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install")
        print(" 2. gcloud auth login")
        print(" 3. gcloud auth application-default login")
        print(" 4. gcloud config set project geoheatai")
        print("\nThen re-run this script.")
        sys.exit(1)
        
    poll_and_download()
