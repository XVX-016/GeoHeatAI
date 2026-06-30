"""
GeoHeatAI — central configuration.

Single source of truth for: target city bounding boxes, GEE collection IDs,
spatial/temporal parameters, and file paths. Import from here rather than
hardcoding values in ingestion scripts.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
TILES_TEMP_DIR = PROJECT_ROOT / "data" / "tiles_temp"

# Ensure directories exist
DATA_RAW.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
TILES_TEMP_DIR.mkdir(parents=True, exist_ok=True)

SERVICE_ACCOUNT_KEY_PATH = Path(
    os.getenv("GEE_SERVICE_ACCOUNT_KEY", PROJECT_ROOT / "config" / "gee-service-account.json")
).expanduser()

# ---------------------------------------------------------------------------
# Google Earth Engine project
# ---------------------------------------------------------------------------
# Set this via the environment, or edit the fallback once your GCP project exists.
GEE_PROJECT_ID = os.getenv("GEE_PROJECT_ID", "geoheatai")

# ---------------------------------------------------------------------------
# Target city — Delhi NCR (primary target for hackathon submission)
# ---------------------------------------------------------------------------
# Bounding box as [west, south, east, north] in WGS84 degrees.
# Covers NCT of Delhi plus a buffer into Gurugram/Noida/Faridabad/Ghaziabad
# to capture peri-urban heat gradient.
CITY_BOUNDS = {
    "delhi_ncr": {
        "bbox": [76.84, 28.40, 77.40, 28.88],  # [west, south, east, north]
        "center": [77.2090, 28.6139],
        "name": "Delhi NCR",
        "utm_epsg": "EPSG:32643",  # UTM Zone 43N — correct UTM zone for Delhi
    },
}

DEFAULT_CITY = "delhi_ncr"

# ---------------------------------------------------------------------------
# Temporal window
# ---------------------------------------------------------------------------
# Pull multiple years to get enough clear-sky Landsat scenes (16-day revisit,
# heavy monsoon cloud loss June-Sept). 2019-2024 avoids COVID-era anomalies
# in some auxiliary datasets while giving ~5 years of scenes.
START_DATE = "2019-01-01"
END_DATE = "2024-12-31"

# Restrict to pre-monsoon/summer months for the core heat analysis
# (this is when UHI signal is strongest and matters most for mitigation).
# Set to None to use the full year instead.
SUMMER_MONTHS = [3, 4, 5, 6]  # March-June, pre-monsoon peak heat in Delhi

# ---------------------------------------------------------------------------
# GEE collection IDs
# ---------------------------------------------------------------------------
COLLECTIONS = {
    "landsat8_sr": "LANDSAT/LC08/C02/T1_L2",
    "landsat9_sr": "LANDSAT/LC09/C02/T1_L2",
    "sentinel2_sr": "COPERNICUS/S2_SR_HARMONIZED",
    "era5_hourly": "ECMWF/ERA5_LAND/HOURLY",
    "dynamic_world": "GOOGLE/DYNAMICWORLD/V1",  # backup LULC if needed
    "ghsl_built_height": "JRC/GHSL/P2023A/GHS_BUILT_H/2018",
    "ghsl_built_surface": "JRC/GHSL/P2023A/GHS_BUILT_S",
}

# ---------------------------------------------------------------------------
# Spatial / quality parameters
# ---------------------------------------------------------------------------
TARGET_RESOLUTION_M = 30  # uniform output grid resolution
CLOUD_COVER_MAX_PCT = 20  # scene-level filter before per-pixel masking
ERA5_TIME_WINDOW_HOURS = 3  # +/- window for matching ERA5 to Landsat overpass

# Landsat 8/9 overpass time over Delhi is ~10:30-10:45 local (~05:00-05:15 UTC)
LANDSAT_OVERPASS_UTC_HOUR_APPROX = 5

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
EXPORT_FOLDER_DRIVE = "GeoHeatAI_Exports"  # Google Drive folder for GEE exports
GCS_BUCKET = "geoheatai-exports"
GCS_PREFIX = "geoheatai_delhi_ncr"
HDF5_TILE_SIZE = 256  # patch size for ML-ready tiles (U-Net input)

