"""
GeoHeatAI — Earth Engine authentication bootstrap.

Run this once after you've created your GCP project, enabled the Earth
Engine API, and downloaded a service account JSON key. It verifies your
credentials work and that you can pull a trivial image, before any real
pipeline code runs against your quota.

Usage:
    python src/utils/gee_auth.py

If this is your first time and you do NOT yet have a service account key,
you can alternatively authenticate interactively (opens a browser) by
calling `ee.Authenticate()` once — see the `interactive_fallback()` function
below. Service account auth is recommended long-term since it doesn't expire
your local session and works unattended.
"""

import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import GEE_PROJECT_ID, SERVICE_ACCOUNT_KEY_PATH


def validate_project_id() -> None:
    """Fail fast if the GCP project ID has not been configured yet."""
    if not GEE_PROJECT_ID or GEE_PROJECT_ID.startswith("CHANGE_ME"):
        raise ValueError(
            "GEE_PROJECT_ID is not configured. Set the GEE_PROJECT_ID environment "
            "variable or update config/config.py before authenticating."
        )


def init_with_service_account() -> None:
    """Authenticate using a downloaded service account JSON key."""
    validate_project_id()

    if not SERVICE_ACCOUNT_KEY_PATH.exists():
        raise FileNotFoundError(
            f"Service account key not found at {SERVICE_ACCOUNT_KEY_PATH}.\n"
            "Download it from GCP Console > IAM & Admin > Service Accounts "
            "and place it at this exact path (it is gitignored)."
        )

    # The service account email is embedded inside the JSON key itself,
    # so ee.ServiceAccountCredentials can read it directly.
    import json

    with open(SERVICE_ACCOUNT_KEY_PATH, encoding="utf-8") as f:
        key_data = json.load(f)
    service_account_email = key_data["client_email"]

    credentials = ee.ServiceAccountCredentials(
        service_account_email, str(SERVICE_ACCOUNT_KEY_PATH)
    )
    ee.Initialize(credentials, project=GEE_PROJECT_ID)


def interactive_fallback() -> None:
    """
    One-time interactive auth (opens browser, stores a local token).
    Use this only if you haven't set up a service account yet and want
    to verify GEE access quickly. Re-run is needed if the token expires.
    """
    validate_project_id()
    ee.Authenticate()  # opens browser, follow the prompt
    ee.Initialize(project=GEE_PROJECT_ID)


def verify_connection() -> None:
    """Pull a trivial image and print metadata to confirm auth + API access."""
    image = ee.Image("USGS/SRTMGL1_003")
    info = image.getInfo()
    band_names = [b["id"] for b in info["bands"]]
    print("✓ Earth Engine connection verified.")
    print(f"  Project: {GEE_PROJECT_ID}")
    print(f"  Test image bands: {band_names}")


if __name__ == "__main__":
    try:
        init_with_service_account()
    except FileNotFoundError as e:
        print(f"⚠ {e}")
        print("\nFalling back to interactive authentication...")
        interactive_fallback()

    verify_connection()
