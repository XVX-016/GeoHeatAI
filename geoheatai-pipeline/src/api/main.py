"""
GeoHeatAI — FastAPI API Server.

Serves baseline temperatures, SHAP attributions, Pareto-optimal intervention strategies,
and provides an endpoint to simulate custom cooling scenarios in real-time.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Optional
import numpy as np
import h5py
import joblib

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import DATA_PROCESSED, DEFAULT_CITY, CITY_BOUNDS

# Target coordinates for Delhi NCR
CITY = DEFAULT_CITY
BBOX = CITY_BOUNDS[CITY]["bbox"]  # [west, south, east, north]
LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = BBOX

app = FastAPI(
    title="GeoHeatAI Pipeline API",
    description="Backend API serving urban heat mitigation ML models, SHAP values, and Pareto optimization.",
    version="1.0.0"
)

# Enable CORS for Next.js frontend (CORS is open for localhost/any origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for caching preloaded data/models
xgb_model = None
lgbm_model = None
ridge_model = None
pareto_data = None
shap_data = None
recommended_data = None

# Baseline grid attributes
baseline_zone_feats = None
baseline_lst = None
means = None
stds = None
band_names = None

# Indices of bands for modifications
ndvi_idx = None
albedo_idx = None
ndwi_idx = None
built_idx = None

class SimulationRequest(BaseModel):
    greening_pct: float
    coolroof_pct: float
    blueinfra_ha: float
    zones: List[int]

class SimulationResponse(BaseModel):
    delta_t_c: float
    hotspots_eliminated: int
    area_treated_km2: float
    cost_cr: float

def compute_zone_averages_api(features: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """Compute baseline features per zone (5x10 grid) from patch features."""
    n_patches, _, _, n_features = features.shape
    lat_step = (LAT_MAX - LAT_MIN) / 5.0
    lon_step = (LON_MAX - LON_MIN) / 10.0

    zone_sums = np.zeros((50, n_features), dtype=np.float64)
    zone_counts = np.zeros(50, dtype=np.int64)

    for i in range(n_patches):
        lat, lon = centroids[i]
        lat_idx = int((lat - LAT_MIN) / lat_step)
        lon_idx = int((lon - LON_MIN) / lon_step)
        
        lat_idx = max(0, min(4, lat_idx))
        lon_idx = max(0, min(9, lon_idx))
        zone_id = lat_idx * 10 + lon_idx
        
        patch_mean = np.mean(features[i], axis=(0, 1))
        zone_sums[zone_id] += patch_mean
        zone_counts[zone_id] += 1

    zone_averages = np.zeros((50, n_features), dtype=np.float32)
    global_mean = np.mean(features, axis=(0, 1, 2))

    for i in range(50):
        if zone_counts[i] > 0:
            zone_averages[i] = zone_sums[i] / zone_counts[i]
        else:
            zone_averages[i] = global_mean

    return zone_averages

@app.on_event("startup")
def load_assets():
    """Pre-load model parameters, SHAP summaries, and Pareto data into memory."""
    # sync load acceptable for local demo
    global xgb_model, lgbm_model, ridge_model, pareto_data, shap_data, recommended_data
    global baseline_zone_feats, baseline_lst, means, stds, band_names
    global ndvi_idx, albedo_idx, ndwi_idx, built_idx

    h5_path = DATA_PROCESSED / "delhi_tiles.h5"
    xgb_path = DATA_PROCESSED / "xgb_model.joblib"
    lgbm_path = DATA_PROCESSED / "lgbm_model.joblib"
    ridge_path = DATA_PROCESSED / "ridge_meta_model.joblib"
    pareto_path = DATA_PROCESSED / "pareto_front.json"
    shap_path = DATA_PROCESSED / "shap_summary.json"
    recommended_path = DATA_PROCESSED / "recommended_intervention.json"

    print("Startup: Pre-loading model parameters...")

    # Load ML models
    if xgb_path.exists():
        xgb_model = joblib.load(xgb_path)
    if lgbm_path.exists():
        lgbm_model = joblib.load(lgbm_path)
    if ridge_path.exists():
        ridge_model = joblib.load(ridge_path)

    # Load static JSON summaries
    if pareto_path.exists():
        with open(pareto_path) as f:
            pareto_data = json.load(f)
    if shap_path.exists():
        with open(shap_path) as f:
            shap_data = json.load(f)
    if recommended_path.exists():
        with open(recommended_path) as f:
            recommended_data = json.load(f)

    # Load features for real-time scenario simulation
    if h5_path.exists() and xgb_model is not None:
        with h5py.File(h5_path, "r") as h5f:
            features = h5f["patches/features"][:]
            centroids = h5f["metadata/centroids"][:]
            means = h5f["metadata/norm_stats/means"][:]
            stds = h5f["metadata/norm_stats/stds"][:]
            band_names = [n.decode("utf-8") for n in h5f["metadata/band_names"][:]]

        # Set indices
        ndvi_idx = band_names.index("NDVI")
        albedo_idx = band_names.index("ALBEDO")
        ndwi_idx = band_names.index("NDWI")
        built_idx = band_names.index("BUILT_SURFACE_FRACTION")

        # Compute average feature values for 5x10 zones
        baseline_zone_feats = compute_zone_averages_api(features, centroids)
        baseline_lst = xgb_model.predict(baseline_zone_feats)

@app.get("/api/health")
def health_check():
    """Service health check endpoint."""
    model_status = "Available" if xgb_model is not None else "Missing ML Models"
    return {
        "status": "ok",
        "model": "XGBoost+PINN",
        "city": "Delhi NCR",
        "ml_model_status": model_status
    }

@app.get("/api/lst/baseline")
def get_baseline_geojson():
    """
    Generate and return a GeoJSON FeatureCollection of the 50 spatial zones
    containing baseline temperatures, hotspot ranks, and top driver features.
    """
    if baseline_zone_feats is None or shap_data is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML models or baseline data not pre-loaded. Please verify processing is complete."
        )

    # Sort zone indexes to determine rank (highest baseline LST = rank 1)
    ranks = np.argsort(baseline_lst)[::-1]
    zone_ranks = np.zeros(50, dtype=int)
    for rank_idx, zone_id in enumerate(ranks):
        zone_ranks[zone_id] = rank_idx + 1

    # Extract top driver globally from SHAP summary
    top_driver_global = shap_data["top_3_drivers"][0]["feature"] if shap_data else "Urban Density"

    # Grid boundaries
    lat_step = (LAT_MAX - LAT_MIN) / 5.0
    lon_step = (LON_MAX - LON_MIN) / 10.0

    features = []
    for i in range(50):
        lat_idx = i // 10
        lon_idx = i % 10

        west = LON_MIN + lon_idx * lon_step
        east = west + lon_step
        south = LAT_MIN + lat_idx * lat_step
        north = south + lat_step

        features.append({
            "type": "Feature",
            "id": f"zone_{i}",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south]
                ]]
            },
            "properties": {
                "zone_id": i,
                "mean_lst_c": float(baseline_lst[i]),
                "max_lst_c": float(baseline_lst[i] + 3.5),  # proxy local maximum
                "hotspot_rank": int(zone_ranks[i]),
                "top_driver": top_driver_global
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.get("/api/drivers")
def get_drivers():
    """Retrieve SHAP drivers and attribution values."""
    if shap_data is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SHAP summary file not found."
        )
    return shap_data

@app.get("/api/pareto")
def get_pareto_front():
    """Retrieve Pareto-optimal spatial strategies array."""
    if pareto_data is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pareto front solutions not found."
        )
    return pareto_data

@app.get("/api/scenarios/recommended")
def get_recommended_scenario():
    """Retrieve the recommended spatial intervention strategy."""
    if recommended_data is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommended strategy data not found."
        )
    return recommended_data

@app.post("/api/scenarios/simulate", response_model=SimulationResponse)
def simulate_scenario(req: SimulationRequest):
    """
    Simulate a custom cooling scenario by modifying physical indices for selected zones,
    evaluating temperatures with the XGBoost model, and returning delta cooling,
    hotspots eliminated, area treated, and cost.
    """
    if xgb_model is None or baseline_zone_feats is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="XGBoost prediction model or baseline features are not loaded."
        )

    # 1. Input Validation
    if not (0 <= req.greening_pct <= 100 and 0 <= req.coolroof_pct <= 100 and 0 <= req.blueinfra_ha <= 100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Intervention percentages must be in the range [0, 100]."
        )

    # Convert percentages to fractions in [0, 1]
    f_green = req.greening_pct / 100.0
    f_cool = req.coolroof_pct / 100.0
    f_blue = req.blueinfra_ha / 100.0

    # Ensure zone IDs exist
    invalid_zones = [z for z in req.zones if not (0 <= z < 50)]
    if invalid_zones:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid zone IDs found: {invalid_zones}. Valid IDs are 0 to 49."
        )

    # 2. Apply modifications to selected zones
    mod_feats = baseline_zone_feats.copy()

    for z in req.zones:
        # Denormalize
        ndvi_raw = mod_feats[z, ndvi_idx] * stds[ndvi_idx] + means[ndvi_idx]
        albedo_raw = mod_feats[z, albedo_idx] * stds[albedo_idx] + means[albedo_idx]
        ndwi_raw = mod_feats[z, ndwi_idx] * stds[ndwi_idx] + means[ndwi_idx]
        built_raw = mod_feats[z, built_idx] * stds[built_idx] + means[built_idx]

        # Apply updates
        ndvi_new = ndvi_raw + 0.20 * f_green
        
        # Cool roofs: only effective where building surface fraction > 0.5
        albedo_new = albedo_raw
        if built_raw > 0.5:
            albedo_new = albedo_raw + 0.45 * f_cool
            
        ndwi_new = ndwi_raw + (0.3 - ndwi_raw) * f_blue

        # Re-normalize
        mod_feats[z, ndvi_idx] = (ndvi_new - means[ndvi_idx]) / stds[ndvi_idx]
        mod_feats[z, albedo_idx] = (albedo_new - means[albedo_idx]) / stds[albedo_idx]
        mod_feats[z, ndwi_idx] = (ndwi_new - means[ndwi_idx]) / stds[ndwi_idx]

    # 3. Model Prediction
    pred_lst = xgb_model.predict(mod_feats)
    delta_t_zone = baseline_lst - pred_lst  # LST reduction (cooling)

    # 4. Compile Metrics
    # Average cooling delta in treated zones
    if len(req.zones) > 0:
        mean_delta_t = float(np.mean(delta_t_zone[req.zones]))
    else:
        mean_delta_t = 0.0

    # Hotspots eliminated
    # Hotspot definition: baseline LST is above the 80th percentile of baseline temps
    hotspot_threshold = np.percentile(baseline_lst, 80)
    
    hotspots_before = np.sum(baseline_lst[req.zones] > hotspot_threshold)
    hotspots_after = np.sum(pred_lst[req.zones] > hotspot_threshold)
    hotspots_eliminated = int(max(0, hotspots_before - hotspots_after))

    # Area treated in km² (Delhi NCR bbox is approx 50km * 50km = 2500 km², each zone is 50 km²)
    zone_area_km2 = 50.0
    area_treated = float(len(req.zones) * zone_area_km2 * (f_green + f_cool + f_blue))

    # Cost in Cr: greening 120 Cr/%, cool roofs 80 Cr/%, blue infra 40 Cr/%
    # Total percentage treated in each zone is (f * 100)
    cost = float(
        len(req.zones) * (
            f_green * 120 * 100 +
            f_cool * 80 * 100 +
            f_blue * 40 * 100
        )
    )

    return SimulationResponse(
        delta_t_c=mean_delta_t,
        hotspots_eliminated=hotspots_eliminated,
        area_treated_km2=area_treated,
        cost_cr=cost
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
