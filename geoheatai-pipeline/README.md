# GeoHeatAI Pipeline

Phase 1 ingestion pipeline for the GeoHeatAI urban heat optimization project.

This package pulls and aligns:

- Landsat 8/9 Collection 2 Level-2 land surface temperature (LST)
- Sentinel-2 NDVI, NDBI, NDWI, and albedo features
- ERA5-Land hourly meteorology aligned to Landsat overpass time
- GHSL built morphology and a documented Sky View Factor proxy
- Optional OpenStreetMap building footprints through Overpass

## First Verified GEE Connection

Follow this sequence before running any export task.

### 1. Get the GCP project ID

Open Google Cloud Console:

```text
https://console.cloud.google.com
```

Use the top-bar project selector and copy the **Project ID**, not just the
display name. It usually looks like `geoheatai-delhi` or
`geoheatai-123456`.

### 2. Download the service-account JSON key

In Google Cloud Console:

```text
IAM & Admin -> Service Accounts -> your service account -> Keys -> Add Key -> Create new key -> JSON
```

Rename the downloaded file to:

```text
gee-service-account.json
```

Place it here:

```text
C:\Computing\GeoHeatAI\geoheatai-pipeline\config\gee-service-account.json
```

Do not commit this file. It is ignored by git.

### 3. Register the service account with Earth Engine

Enabling the Earth Engine API in Google Cloud is not enough. The service
account email must also be registered with Earth Engine.

Open the JSON key and copy the `client_email` value. It looks like:

```text
something@geoheatai-delhi.iam.gserviceaccount.com
```

Register that service account through Earth Engine:

```text
https://code.earthengine.google.com/register
https://developers.google.com/earth-engine/guides/service_account
```

If you skip this step, auth usually fails with `403` or `Permission denied`.

### 4. Create the Python environment

Run from this folder:

```powershell
cd C:\Computing\GeoHeatAI\geoheatai-pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, allow local scripts for the current user:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

If you do not want to change execution policy, call the venv Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 5. Set the project ID and verify auth

```powershell
$env:GEE_PROJECT_ID = "your-actual-project-id-here"
python src/utils/gee_auth.py
```

Expected output:

```text
Earth Engine connection verified.
  Project: your-actual-project-id-here
  Test image bands: ['elevation']
```

If your key lives somewhere else:

```powershell
$env:GEE_SERVICE_ACCOUNT_KEY = "C:\path\to\gee-service-account.json"
```

The fallback values are in `config/config.py`, but environment variables are
preferred for local runs.

## Dry-Run Scene Count

After auth succeeds, run the dry run. The orchestrator defaults to
`dry_run=True`, so it lists candidate Landsat scenes without starting export
tasks.

```powershell
python src/ingestion/run_pipeline.py
```

Expected range for summer months 2019-2024 over Delhi NCR after cloud
filtering is roughly 60-120 Landsat scenes. Review the scene count and dates.
When they look right, edit the bottom of `src/ingestion/run_pipeline.py` and
call:

```python
run_phase1_export(dry_run=False, max_scenes=10)
```

Exports are submitted as Google Earth Engine batch tasks to Google Drive.
Monitor them at:

```text
https://code.earthengine.google.com/tasks
```

## Troubleshooting

- `Earth Engine client is not initialized`: `gee_auth.py` was not called before
  Earth Engine functions ran. Check that `run_pipeline.py` calls
  `init_with_service_account()` inside `__main__`.
- `Permission denied` or `403`: the service account is probably not registered
  in Earth Engine. Re-check step 3.
- `Project not found`: `$env:GEE_PROJECT_ID` does not exactly match the Project
  ID in Google Cloud Console.
- `GEE_PROJECT_ID is not configured`: set `$env:GEE_PROJECT_ID` or update the
  fallback in `config/config.py`.

## Safety Notes

- Keep `dry_run=True` until the scene list looks correct.
- `config/gee-service-account.json` is ignored by git.
- `data/raw` and `data/processed` are ignored except for `.gitkeep` files.
- ERA5 variables are bilinearly resampled because atmospheric fields vary
  smoothly at the scale of this project.
- `SVF_PROXY` is not a true ray-traced Sky View Factor; it is a first-order
  approximation from GHSL height and built surface fraction.


hehehehhe