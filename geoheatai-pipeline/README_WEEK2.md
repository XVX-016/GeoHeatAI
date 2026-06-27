# GeoHeatAI — Phase 2 & 3 Development Documentation

This documentation covers GCS exports, data tiling, machine learning baseline models (XGBoost + LightGBM), deep physical modeling (PINN U-Net), multi-objective optimization (NSGA-III), and the FastAPI API server configuration.

---

## 0. GCS Export Setup (replaces Google Drive)
To resolve Google Drive storage limit issues, scene exports are sent to Google Cloud Storage (GCS).

1. **Install and Authenticate gcloud CLI**:
   - Install the gcloud CLI: https://cloud.google.com/sdk/docs/install
   - Log in and configure application default credentials:
     ```bash
     gcloud auth login
     gcloud auth application-default login
     gcloud config set project geoheatai
     ```
2. **Initialize Bucket & Permissions**:
   ```bash
   python setup_gcs.py
   ```
3. **Resubmit Failed Tasks to GCS**:
   ```bash
   python src/ingestion/run_pipeline.py --resubmit-failed
   ```
4. **Poll and Download GeoTIFFs**:
   ```bash
   python src/utils/download_from_gcs.py
   ```
5. **Run the Complete Pipeline**:
   Once all files are downloaded, execute the full pipeline runner:
   ```bash
   python src/utils/pipeline_runner.py
   ```

---

## 1. Data Preprocessing & Tiling
Once the 133 Landsat scenes are finished exporting from Google Earth Engine and downloaded to your local machine:
1. Place the multi-band `.tif` files in the folder `geoheatai-pipeline/data/raw/`.
2. Run the tiling script to slice files into standardized overlaps and normalize features:
   ```bash
   python src/preprocessing/tile_to_hdf5.py
   ```
* **Output**:
  - `data/processed/delhi_tiles.h5` containing spatial patches `/patches/features` (normalized features) and `/patches/labels` (raw LST_C labels), alongside normalisation metadata and coordinates.
  - Slices are 256x256 pixels with 32px overlap. Patches with >20% masked pixels are automatically discarded.

---

## 2. Tabular ML Baseline (XGBoost + LightGBM Stacking)
Evaluate baseline temperature prediction using spatial leave-one-zone-out cross-validation:
```bash
python src/ml/xgboost_baseline.py
```
* **How it works**:
  - Automatically maps each patch to one of 9 spatial zones in a 3x3 grid spanning Delhi NCR.
  - Performs 9-fold spatial cross-validation (training on 8 zones, validating on 1, rotating) to prevent spatial autocorrelation leakage.
  - Trains XGBoost and LightGBM regressors, stacking predictions using a Ridge meta-learner.
  - Fits a `shap.TreeExplainer` on the final full-trained XGBoost model.
* **Outputs**:
  - Prints the Top 3 physical drivers of urban heat (e.g. built density, albedo, green index).
  - Saves SHAP summary statistics to `data/processed/shap_summary.json`.
  - Serializes models to `data/processed/xgb_model.joblib`, `data/processed/lgbm_model.joblib`, and `data/processed/ridge_meta_model.joblib`.

---

## 3. Deep Physics-Informed U-Net (PINN)
Train the physical neural network with the custom Surface Energy Balance (SEB) loss constraint:
```bash
python src/ml/pinn_unet.py
```
* **How it works**:
  - U-Net channels: 14/18 (features) -> 64 -> 128 -> 256 -> 512 -> 1024 (bottleneck) -> decoders -> 1 (predicted LST).
  - Custom loss function: `Loss = MSE_LST + 0.1 * SEB_penalty`
  - Bowen Ratio proxy $B = H / (H + LE)$ is calculated per pixel. High-NDVI vegetation pixels are penalized if $B > 0.6$ (should be latent-heat dominated), and built-up pixels are penalized if $B < 0.4$ (should be sensible-heat dominated).
* **Execution Details**:
  - **Expected Training Time**: ~2-3 hours on an NVIDIA RTX 4060 GPU.
  - Implements mixed-precision training and saves the best checkpoint to `data/processed/pinn_unet_best.pt`.
  - Exports a tracing-compatible TorchScript compilation to `data/processed/pinn_unet.torchscript`.

---

## 4. Multi-Objective Intervention Optimization (NSGA-III)
Evaluate urban greening, cool roofs, and blue infrastructure strategies using NSGA-III:
```bash
python src/optimization/nsga3_optimizer.py
```
* **How it works**:
  - Models Delhi NCR as 50 spatial zones (5x10 grid).
  - Defines 150 continuous decision variables (greening, cool roof, and blue infrastructure fractions in $[0, 1]$ per zone).
  - Solves the multi-objective problem (minimize negated average cooling delta, minimize cost in Crores, and minimize inequity/spatial standard deviation).
  - **Expected Runtime**: ~15-20 minutes.
* **Outputs**:
  - Saves all non-dominated strategies to `data/processed/pareto_front.json`.
  - Recommends the highest cooling strategy matching `cost < 25000 Cr` and saves it to `data/processed/recommended_intervention.json`.

---

## 5. Running and Testing the FastAPI Backend
Start the FastAPI server to serve predictions and support real-time scenario simulation:
```bash
python src/api/main.py
```
The server will run on `http://localhost:8000/`.

### Test Endpoints via `curl`:
* **Health Check**:
  ```bash
  curl http://localhost:8000/api/health
  ```
* **Baseline Zone GeoJSON**:
  ```bash
  curl http://localhost:8000/api/lst/baseline
  ```
* **SHAP Driver Importance**:
  ```bash
  curl http://localhost:8000/api/drivers
  ```
* **Pareto Front**:
  ```bash
  curl http://localhost:8000/api/pareto
  ```
* **Scenario Custom Simulation**:
  Simulate greening and cool roofs over specific zones (e.g. zones 10, 11, 12):
  ```bash
  curl -X POST http://localhost:8000/api/scenarios/simulate \
       -H "Content-Type: application/json" \
       -d '{"greening_pct": 15.0, "coolroof_pct": 20.0, "blueinfra_ha": 5.0, "zones": [10, 11, 12]}'
  ```

---

## 6. Frontend Integration
CORS is fully enabled on the FastAPI API backend, allowing all origins. The Next.js frontend is configured to call this backend directly at `http://localhost:8000/` for dynamic dashboards, maps, and simulations.
