"""
GeoHeatAI — Download completed GeoTIFF exports from Google Drive.

Polls the GeoHeatAI_Exports folder in the authenticated user's Drive,
downloads all .tif files to data/raw/, and prints progress.

Uses the Google Drive API with the same personal OAuth credentials
that Earth Engine uses — NOT the service account (service accounts
lack Drive storage quota and cannot own files).

First-time setup:
  1) Go to GCP Console > APIs & Services > Credentials
  2) Create Credentials > OAuth client ID > Desktop app
  3) Download the JSON file
  4) Save it as: geoheatai-pipeline/config/drive_oauth_client.json
  5) Run this script — it will open a browser for one-time consent

Usage:
    python src/utils/download_from_drive.py
"""

import io
import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import DATA_RAW, EXPORT_FOLDER_DRIVE, PROJECT_ROOT

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
OAUTH_CLIENT_SECRETS = PROJECT_ROOT / "config" / "drive_oauth_client.json"
TOKEN_PATH = PROJECT_ROOT / "config" / "drive_token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

EXPECTED_FILE_COUNT = 133  # total scenes submitted to GEE


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def get_drive_service():
    """Build and return an authenticated Google Drive API v3 service.

    On first run, opens a browser for OAuth consent and caches the
    refresh token at config/drive_token.json so subsequent runs are
    headless.
    """
    if not OAUTH_CLIENT_SECRETS.exists():
        print(
            "\n"
            "ERROR: OAuth 2.0 client credentials not found.\n"
            "\n"
            "Download them from:\n"
            "  GCP Console > APIs & Services > Credentials\n"
            "  > Create Credentials > OAuth client ID > Desktop app\n"
            "  > Download JSON\n"
            "\n"
            f"Save as: {OAUTH_CLIENT_SECRETS}\n"
            "\n"
            "Then re-run this script.\n"
        )
        sys.exit(1)

    creds = None

    # Load cached token if it exists
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or run full OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(OAUTH_CLIENT_SECRETS), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Persist for next run
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        print(f"OAuth token saved to {TOKEN_PATH}")

    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Drive helpers
# ---------------------------------------------------------------------------
def _find_folder_id(service, folder_name: str) -> str | None:
    """Return the Drive folder ID for the given folder name, or None."""
    resp = (
        service.files()
        .list(
            q=f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            spaces="drive",
            fields="files(id, name)",
            pageSize=10,
        )
        .execute()
    )
    folders = resp.get("files", [])
    if not folders:
        return None
    return folders[0]["id"]


def list_export_files(service) -> list[dict]:
    """Return a list of {id, name, size} dicts for all .tif files
    inside the GeoHeatAI_Exports folder on Drive.
    """
    folder_id = _find_folder_id(service, EXPORT_FOLDER_DRIVE)
    if not folder_id:
        print(f"WARNING: Drive folder '{EXPORT_FOLDER_DRIVE}' not found.")
        return []

    files: list[dict] = []
    page_token = None

    while True:
        resp = (
            service.files()
            .list(
                q=(
                    f"'{folder_id}' in parents"
                    " and mimeType != 'application/vnd.google-apps.folder'"
                    " and trashed = false"
                    " and name contains '.tif'"
                ),
                spaces="drive",
                fields="nextPageToken, files(id, name, size)",
                pageSize=100,
                pageToken=page_token,
            )
            .execute()
        )
        for f in resp.get("files", []):
            files.append(
                {
                    "id": f["id"],
                    "name": f["name"],
                    "size": int(f.get("size", 0)),
                }
            )
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return files


def download_file(
    service, file_id: str, file_name: str, dest_dir: Path
) -> bool:
    """Download a single file from Drive to dest_dir.

    Skips the download if a local file with the same name and size
    already exists. Returns True if a new file was downloaded.
    """
    dest_path = dest_dir / file_name

    # Check if already downloaded with matching size
    if dest_path.exists():
        local_size = dest_path.stat().st_size
        # Fetch remote size for comparison
        meta = (
            service.files().get(fileId=file_id, fields="size").execute()
        )
        remote_size = int(meta.get("size", 0))
        if local_size == remote_size:
            return False  # already up to date

    request = service.files().get_media(fileId=file_id)

    # Stream to a temp file, then rename on success
    tmp_path = dest_path.with_suffix(".tif.part")
    with open(tmp_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=10 * 1024 * 1024)

        # Get total size for progress bar
        meta = service.files().get(fileId=file_id, fields="size").execute()
        total_bytes = int(meta.get("size", 0))

        with tqdm(
            total=total_bytes,
            unit="B",
            unit_scale=True,
            desc=file_name[:50],
            leave=True,
        ) as pbar:
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    pbar.update(status.resumable_progress - pbar.n)
            pbar.update(pbar.total - pbar.n)  # ensure bar hits 100%

    tmp_path.rename(dest_path)
    return True


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------
def poll_and_download(interval_minutes: int = 5) -> None:
    """Poll Drive every *interval_minutes*, download new .tif files,
    and stop when file count hasn't changed for 2 consecutive polls
    (meaning all exports have landed).
    """
    print(f"Target folder: {EXPORT_FOLDER_DRIVE}")
    print(f"Download dir:  {DATA_RAW}")
    print(f"Poll interval: {interval_minutes} min\n")

    DATA_RAW.mkdir(parents=True, exist_ok=True)

    service = get_drive_service()
    prev_count = -1
    stable_polls = 0

    while True:
        remote_files = list_export_files(service)
        current_count = len(remote_files)
        print(f"\n{'='*60}")
        print(f"  {current_count}/{EXPECTED_FILE_COUNT} files in Drive")

        # Download any new/missing files
        downloaded = 0
        for f in remote_files:
            if download_file(service, f["id"], f["name"], DATA_RAW):
                downloaded += 1

        local_tifs = list(DATA_RAW.glob("geoheatai_*.tif"))
        print(f"  {len(local_tifs)}/{EXPECTED_FILE_COUNT} files downloaded locally")

        if downloaded > 0:
            print(f"  ({downloaded} new files this poll)")

        # Check stability — stop after 2 polls with no new files
        if current_count == prev_count and current_count > 0:
            stable_polls += 1
        else:
            stable_polls = 0
        prev_count = current_count

        if stable_polls >= 2:
            print(f"\n✓ File count stable for {stable_polls} consecutive polls.")
            print(f"  Total: {len(local_tifs)} GeoTIFFs downloaded to {DATA_RAW}")
            break

        if current_count >= EXPECTED_FILE_COUNT:
            print(f"\n✓ All {EXPECTED_FILE_COUNT} files accounted for.")
            print(f"  Total: {len(local_tifs)} GeoTIFFs downloaded to {DATA_RAW}")
            break

        print(f"\n  Waiting {interval_minutes} minutes before next poll...")
        time.sleep(interval_minutes * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("GeoHeatAI — Drive Export Downloader\n")
    poll_and_download()
    print("\n" + "=" * 60)
    print("All exports downloaded. Run:")
    print("  python src/preprocessing/tile_to_hdf5.py")
