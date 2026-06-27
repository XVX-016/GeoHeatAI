"""
GeoHeatAI — XGBoost + LightGBM baseline with spatial cross-validation.

Loads HDF5 patch tiles, flattens spatial patches to tabular rows, and trains
a stacked ensemble (XGBoost + LightGBM with Ridge meta-learner). Uses spatial
leave-one-zone-out cross-validation to prevent autocorrelation leakage, and
explains model attributions using SHAP.
"""

import os
import sys
import json
from pathlib import Path
import numpy as np
import h5py
import joblib
from sklearn.model_selection import KFold
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import xgboost as xgb
import lightgbm as lgb
import shap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import DATA_PROCESSED, DEFAULT_CITY, CITY_BOUNDS

# Target city coordinates for spatial zones
CITY = DEFAULT_CITY
BBOX = CITY_BOUNDS[CITY]["bbox"]  # [west, south, east, north]
LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = BBOX

def assign_spatial_zones(centroids: np.ndarray) -> np.ndarray:
    """
    Split the Delhi NCR bounding box into a 3x3 grid (9 zones).
    Assigns each patch index to a zone from 0 to 8 based on centroid lat/lon.
    """
    lon_width = LON_MAX - LON_MIN
    lat_height = LAT_MAX - LAT_MIN
    
    lon_step = lon_width / 3.0
    lat_step = lat_height / 3.0

    zones = []
    for lat, lon in centroids:
        lon_idx = int((lon - LON_MIN) / lon_step)
        lat_idx = int((lat - LAT_MIN) / lat_step)
        
        # Clamp index boundaries to [0, 2]
        lon_idx = max(0, min(2, lon_idx))
        lat_idx = max(0, min(2, lat_idx))
        
        zone_id = lat_idx * 3 + lon_idx
        zones.append(zone_id)
        
    return np.array(zones)

def train_stacked_ensemble(X_train, y_train, X_val):
    """
    Train XGBoost and LightGBM regressors on the training set, generate
    out-of-fold predictions to fit a Ridge meta-learner, and predict on validation.
    """
    # 1. Generate out-of-fold features for the Ridge meta-learner
    inner_cv = KFold(n_splits=3, shuffle=True, random_state=42)
    oof_predictions = np.zeros((X_train.shape[0], 2)) # cols: xgb, lgbm
    
    for train_idx, val_idx in inner_cv.split(X_train):
        X_tr, y_tr = X_train[train_idx], y_train[train_idx]
        X_va = X_train[val_idx]
        
        # Inner models
        m_xgb = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
        m_lgb = lgb.LGBMRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1, verbose=-1)
        
        m_xgb.fit(X_tr, y_tr)
        m_lgb.fit(X_tr, y_tr)
        
        oof_predictions[val_idx, 0] = m_xgb.predict(X_va)
        oof_predictions[val_idx, 1] = m_lgb.predict(X_va)

    # Fit Ridge meta-learner
    meta_learner = Ridge(alpha=1.0)
    meta_learner.fit(oof_predictions, y_train)

    # 2. Fit final base models on all training data
    final_xgb = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
    final_lgb = lgb.LGBMRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1, verbose=-1)
    
    final_xgb.fit(X_train, y_train)
    final_lgb.fit(X_train, y_train)

    # 3. Predict on validation
    pred_xgb = final_xgb.predict(X_val)
    pred_lgb = final_lgb.predict(X_val)
    
    val_meta_features = np.column_stack([pred_xgb, pred_lgb])
    final_preds = meta_learner.predict(val_meta_features)

    return final_preds, final_xgb, final_lgb, meta_learner

def main():
    h5_path = DATA_PROCESSED / "delhi_tiles.h5"
    if not h5_path.exists():
        print(f"ERROR: HDF5 dataset not found at {h5_path}.")
        print("Please run src/preprocessing/tile_to_hdf5.py first.")
        sys.exit(1)

    print(f"Loading datasets from {h5_path}...")
    with h5py.File(h5_path, "r") as h5f:
        # Shapes: features (N, 256, 256, 14), labels (N, 256, 256, 1)
        features = h5f["patches/features"][:]
        labels = h5f["patches/labels"][:]
        
        # Metadata
        band_names = [n.decode("utf-8") for n in h5f["metadata/band_names"][:]]
        centroids = h5f["metadata/centroids"][:]

    n_patches = features.shape[0]
    patch_h, patch_w, n_features = features.shape[1:]

    print(f"Loaded {n_patches} patches. Features: {n_features} bands, Labels: {labels.shape[-1]} bands.")

    # Assign zones based on centroid coordinates
    spatial_split_available = True
    if centroids.shape[0] != n_patches:
        print("WARNING: Centroid count does not match patch count. Falling back to sequential K-Fold.")
        spatial_split_available = False
        zones = np.zeros(n_patches)
    else:
        zones = assign_spatial_zones(centroids)
        unique_zones, zone_counts = np.unique(zones, return_counts=True)
        print("Patches per spatial zone:")
        for z, c in zip(unique_zones, zone_counts):
            print(f"  Zone {z}: {c} patches")

    # Spatial CV Loop (Leave-One-Zone-Out)
    r2_scores = []
    rmse_scores = []
    mae_scores = []
    
    # 9-fold spatial cross-validation
    if spatial_split_available:
        n_folds = 9
        folds_to_run = range(9)
    else:
        n_folds = 9
        folds_to_run = range(9)
        # Fall back to sequential 9-fold CV
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        cv_splits = list(kf.split(np.arange(n_patches)))

    print(f"\nStarting {n_folds}-fold spatial leave-one-zone-out cross-validation...")

    for fold in folds_to_run:
        if spatial_split_available:
            train_patch_indices = np.where(zones != fold)[0]
            val_patch_indices = np.where(zones == fold)[0]
            if len(val_patch_indices) == 0:
                print(f"  Fold {fold+1}/{n_folds} (Zone {fold}) skipped because it is empty.")
                continue
        else:
            train_patch_indices, val_patch_indices = cv_splits[fold]

        # Extract patches
        feat_train = features[train_patch_indices]
        label_train = labels[train_patch_indices]
        feat_val = features[val_patch_indices]
        label_val = labels[val_patch_indices]

        # Flatten patches to tabular pixel rows
        X_train = feat_train.reshape(-1, n_features)
        y_train = label_train.reshape(-1)
        X_val = feat_val.reshape(-1, n_features)
        y_val = label_val.reshape(-1)

        # Train stacking regressor
        preds, _, _, _ = train_stacked_ensemble(X_train, y_train, X_val)

        # Calculate metrics
        r2 = r2_score(y_val, preds)
        rmse = np.sqrt(mean_squared_error(y_val, preds))
        mae = mean_absolute_error(y_val, preds)

        r2_scores.append(r2)
        rmse_scores.append(rmse)
        mae_scores.append(mae)

        print(f"  Fold {fold+1}/{n_folds}: R² = {r2:.4f}, RMSE = {rmse:.4f}°C, MAE = {mae:.4f}°C")

    # Output cross-validation summary
    print("\nSpatial CV Results (Stacked Ensemble):")
    print(f"  Mean R²   = {np.mean(r2_scores):.4f} ± {np.std(r2_scores):.4f}")
    print(f"  Mean RMSE = {np.mean(rmse_scores):.4f} ± {np.std(rmse_scores):.4f}°C")
    print(f"  Mean MAE  = {np.mean(mae_scores):.4f} ± {np.std(mae_scores):.4f}°C")

    # Retrain on the ENTIRE dataset for the final model
    print("\nRetraining models on full dataset...")
    X_full = features.reshape(-1, n_features)
    y_full = labels.reshape(-1)

    # Train final stacked ensemble
    _, final_xgb, final_lgb, final_ridge = train_stacked_ensemble(X_full, y_full, X_full)

    # Compute SHAP values using shap.TreeExplainer on the final XGBoost model
    print("Computing SHAP feature importance...")
    # TreeExplainer is fast, but explaining millions of pixels is slow.
    # We sample 5,000 pixels randomly to calculate background/attributions.
    np.random.seed(42)
    sample_indices = np.random.choice(X_full.shape[0], size=5000, replace=False)
    X_sample = X_full[sample_indices]

    explainer = shap.TreeExplainer(final_xgb)
    shap_values = explainer.shap_values(X_sample)

    # Calculate feature importances
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
    sorted_idx = np.argsort(mean_abs_shap)[::-1]

    # Print top-3 drivers
    print("\nTop 3 Urban Heat Drivers (SHAP Importance):")
    top_3_drivers = []
    for i in range(min(3, len(sorted_idx))):
        feat_name = band_names[sorted_idx[i]]
        val = mean_abs_shap[sorted_idx[i]]
        top_3_drivers.append({"feature": feat_name, "mean_abs_shap_value": float(val)})
        print(f"  [{i+1}] {feat_name}: {val:.4f}°C mean impact")

    # Save outputs
    # 1. SHAP Summary JSON
    shap_summary = {
        "feature_names": band_names,
        "mean_abs_shap": mean_abs_shap.tolist(),
        "top_3_drivers": top_3_drivers
    }
    
    summary_path = DATA_PROCESSED / "shap_summary.json"
    with open(summary_path, "w") as f:
        json.dump(shap_summary, f, indent=2)
    print(f"\nSaved SHAP summary to {summary_path}")

    # 2. Serialize Models
    joblib.dump(final_xgb, DATA_PROCESSED / "xgb_model.joblib")
    joblib.dump(final_lgb, DATA_PROCESSED / "lgbm_model.joblib")
    joblib.dump(final_ridge, DATA_PROCESSED / "ridge_meta_model.joblib")
    print(f"Saved serialization models to {DATA_PROCESSED}")

    # 3. Save Metrics for Pipeline Runner
    xgb_metrics = {
        "mean_r2": float(np.mean(r2_scores)),
        "mean_rmse": float(np.mean(rmse_scores)),
        "mean_mae": float(np.mean(mae_scores))
    }
    metrics_path = DATA_PROCESSED / "xgb_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(xgb_metrics, f, indent=2)
    print(f"Saved XGBoost metrics to {metrics_path}")

    return xgb_metrics

if __name__ == "__main__":
    main()

