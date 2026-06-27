"""
GeoHeatAI — Full Week 2 Pipeline Runner.

Orchestrates the entire pipeline sequentially:
1. Checks data/raw/ for GeoTIFF files.
2. Checks if data/processed/delhi_tiles.h5 exists, otherwise runs tile_to_hdf5.py.
3. Checks if data/processed/xgb_model.joblib exists, otherwise runs xgboost_baseline.py.
4. Checks if data/processed/pinn_unet_best.pt exists, otherwise runs pinn_unet.py.
5. Checks if data/processed/pareto_front.json exists, otherwise runs nsga3_optimizer.py.

At the end, displays a comprehensive execution summary table.
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime
import importlib
import h5py

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.config import DATA_RAW, DATA_PROCESSED

def get_timestamp() -> str:
    """Return current timestamp in a readable format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_step(step_name: str, module_path: str, output_file: Path) -> dict | None:
    """
    Run a pipeline step if its output file does not exist.
    Returns the step's return value (if any) or None.
    """
    if output_file.exists():
        print(f"[{get_timestamp()}] [SKIP] Step '{step_name}': Output '{output_file.name}' already exists.")
        return None

    print(f"\n{'='*80}")
    print(f"[{get_timestamp()}] [START] Step '{step_name}'")
    print(f"Running module: {module_path}")
    print(f"{'='*80}\n")

    start_time = time.time()
    try:
        # Dynamically import the module and run its main function
        module = importlib.import_module(module_path)
        result = module.main()
        
        elapsed = time.time() - start_time
        print(f"\n{'='*80}")
        print(f"[{get_timestamp()}] [SUCCESS] Step '{step_name}' completed in {elapsed:.2f} seconds.")
        print(f"{'='*80}\n")
        
        return {
            "elapsed_time": elapsed,
            "result": result
        }
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"[{get_timestamp()}] [FAILURE] Step '{step_name}' failed with error: {e}")
        print(f"{'='*80}\n")
        sys.exit(1)

def main():
    print(f"[{get_timestamp()}] Starting GeoHeatAI Week 2 Pipeline Runner...")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data raw:     {DATA_RAW}")
    print(f"Data proc:    {DATA_PROCESSED}\n")

    # Step 1: Check data/raw/ for GeoTIFF files
    tif_files = list(DATA_RAW.glob("geoheatai_*.tif"))
    if not tif_files:
        # Fall back to checking any .tif in subfolders
        tif_files = list(DATA_RAW.glob("**/*.tif"))

    if not tif_files:
        print(f"[{get_timestamp()}] [ERROR] No GeoTIFF files found in {DATA_RAW}.")
        print("Please download your Google Drive exports to data/raw/ before running the pipeline.")
        sys.exit(1)

    print(f"[{get_timestamp()}] Found {len(tif_files)} GeoTIFF files in {DATA_RAW}.")

    # Step 2: Tiling & HDF5 Processing
    h5_file = DATA_PROCESSED / "delhi_tiles.h5"
    run_step(
        step_name="Spatial Tiling & HDF5 Ingestion",
        module_path="src.preprocessing.tile_to_hdf5",
        output_file=h5_file
    )

    # Step 3: XGBoost Baseline stacked ensemble training
    xgb_model_file = DATA_PROCESSED / "xgb_model.joblib"
    run_step(
        step_name="XGBoost Stacked Baseline Training",
        module_path="src.ml.xgboost_baseline",
        output_file=xgb_model_file
    )

    # Step 4: PINN U-Net training
    pinn_model_file = DATA_PROCESSED / "pinn_unet_best.pt"
    run_step(
        step_name="PINN U-Net Training (PyTorch)",
        module_path="src.ml.pinn_unet",
        output_file=pinn_model_file
    )

    # Step 5: Multi-Objective Spatial Intervention Optimization (NSGA-III)
    pareto_file = DATA_PROCESSED / "pareto_front.json"
    run_step(
        step_name="NSGA-III Spatial Optimization",
        module_path="src.optimization.nsga3_optimizer",
        output_file=pareto_file
    )

    # -------------------------------------------------------------------------
    # Gather metrics for final summary
    # -------------------------------------------------------------------------
    print(f"\n{'='*80}")
    print(f"[{get_timestamp()}] Pipeline complete. Start API with: python src/api/main.py")
    print(f"{'='*80}\n")

    # 1. HDF5 patches
    n_patches = 0
    if h5_file.exists():
        try:
            with h5py.File(h5_file, "r") as h5f:
                n_patches = h5f["patches/features"].shape[0]
        except Exception:
            n_patches = "Error reading HDF5"

    # 2. XGBoost R2
    xgb_r2 = "N/A"
    xgb_metrics_file = DATA_PROCESSED / "xgb_metrics.json"
    if xgb_metrics_file.exists():
        try:
            with open(xgb_metrics_file, "r") as f:
                metrics = json.load(f)
                xgb_r2 = f"{metrics.get('mean_r2', 0.0):.4f}"
        except Exception:
            pass

    # 3. PINN val RMSE
    pinn_rmse = "N/A"
    pinn_metrics_file = DATA_PROCESSED / "pinn_metrics.json"
    if pinn_metrics_file.exists():
        try:
            with open(pinn_metrics_file, "r") as f:
                metrics = json.load(f)
                pinn_rmse = f"{metrics.get('val_rmse', 0.0):.4f}°C"
        except Exception:
            pass

    # 4. Pareto solutions
    n_pareto = 0
    if pareto_file.exists():
        try:
            with open(pareto_file, "r") as f:
                pareto_data = json.load(f)
                n_pareto = len(pareto_data)
        except Exception:
            n_pareto = "Error reading Pareto"

    # 5. Recommended intervention details
    rec_file = DATA_PROCESSED / "recommended_intervention.json"
    rec_delta_t = "N/A"
    rec_cost = "N/A"
    if rec_file.exists():
        try:
            with open(rec_file, "r") as f:
                rec_data = json.load(f)
                rec_delta_t = f"-{rec_data.get('delta_t_c', 0.0):.1f}°C"
                cost_cr = rec_data.get('cost_cr', 0.0)
                rec_cost = f"₹{cost_cr:,.0f} Cr"
        except Exception:
            pass

    # Output Summary Table
    print("================================================================================")
    print("                             PIPELINE EXECUTION SUMMARY                         ")
    print("================================================================================")
    print(f" - TIF files processed  : {len(tif_files)}")
    print(f" - HDF5 patches         : {n_patches}")
    print(f" - XGBoost spatial CV R²: {xgb_r2}")
    print(f" - PINN val RMSE        : {pinn_rmse}")
    print(f" - Pareto solutions     : {n_pareto}")
    print(f" - Recommended ΔT       : {rec_delta_t} at {rec_cost}")
    print("================================================================================")

if __name__ == "__main__":
    main()
