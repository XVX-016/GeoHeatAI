# GeoHeatAI
Physics-informed urban heat intelligence — geospatial AI system 
for identifying heat stress hotspots and generating optimized 
cooling interventions.

**Live demo:** https://geo-heat-ai.vercel.app

## What it does
- Ingests Landsat 8/9 LST, Sentinel-2 NDVI/NDBI, ERA5 
  meteorology, and GHSL urban morphology via Google Earth Engine
- Trains XGBoost + LightGBM ensemble with spatial 
  leave-one-zone-out cross-validation
- Physics-informed U-Net with Surface Energy Balance loss 
  (Rn = G + H + LE)
- NSGA-III multi-objective optimizer (cost vs ΔT vs equity)
- FastAPI backend + Next.js dashboard with MapLibre GL

## Stack
Python: GEE API, PyTorch, XGBoost, LightGBM, SHAP, pymoo, FastAPI
Frontend: Next.js 14, TanStack Router, Recharts, Tailwind CSS

## Run locally
```bash
cd geoheatai-pipeline
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/utils/pipeline_runner.py
python src/api/main.py

cd .. && npm install && npm run dev
```

## Target city
Delhi NCR — 76.84°E to 77.40°E, 28.40°N to 28.88°N
30m spatial resolution, summer months 2019-2024
