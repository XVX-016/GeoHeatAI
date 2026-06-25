"""
GeoHeatAI — Multi-objective spatial intervention optimization via NSGA-III.

Loads the trained tabular XGBoost model, establishes a 5x10 spatial grid
covering Delhi NCR, and uses the pymoo implementation of NSGA-III to find
the Pareto-optimal distribution of cooling interventions.
"""

import os
import sys
import json
from pathlib import Path
import numpy as np
import h5py
import joblib

from pymoo.core.problem import Problem
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.util.ref_dirs import get_reference_directions
from pymoo.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import DATA_PROCESSED, DEFAULT_CITY, CITY_BOUNDS

# Target city coordinates for spatial zones
CITY = DEFAULT_CITY
BBOX = CITY_BOUNDS[CITY]["bbox"]  # [west, south, east, north]
LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = BBOX

class UrbanHeatOptimizationProblem(Problem):
    """
    Vectorized Multi-Objective Optimization Problem.
    150 Decision Variables: 50 zones * 3 interventions (greening, cool roofs, blue infra).
    3 Objectives (all minimized):
      1. Negated temperature reduction (-delta LST)
      2. Implementation cost (Cr)
      3. Temperature inequity (std deviation of LST reduction across zones)
    Constraints:
      1. Mean area treated across all zones <= 15%
      2. For each zone, sum of fractions <= 1.0
    """
    def __init__(
        self,
        xgb_model,
        baseline_zone_feats: np.ndarray,
        band_names: list[str],
        means: np.ndarray,
        stds: np.ndarray
    ):
        # 150 variables: 50 zones * 3 interventions
        # [f_green_0, f_cool_0, f_blue_0, ..., f_green_49, f_cool_49, f_blue_49]
        super().__init__(
            n_var=150,
            n_obj=3,
            n_ieq_constr=51,  # 1 area constraint + 50 per-zone sum constraints
            xl=0.0,
            xu=1.0
        )
        self.xgb_model = xgb_model
        self.baseline_zone_feats = baseline_zone_feats  # shape (50, 18)
        self.band_names = band_names
        self.means = means
        self.stds = stds
        
        # Locate indices in the 18 features (after LST was removed)
        self.ndvi_idx = band_names.index("NDVI")
        self.albedo_idx = band_names.index("ALBEDO")
        self.ndwi_idx = band_names.index("NDWI")
        self.built_idx = band_names.index("BUILT_SURFACE_FRACTION")

        # Precompute baseline temperature for each zone
        self.baseline_lst = self.xgb_model.predict(baseline_zone_feats)

    def _evaluate(self, X, out, *args, **kwargs):
        pop_size = X.shape[0]
        
        # Reshape X to (pop_size, 50, 3)
        X_reshaped = X.reshape(pop_size, 50, 3)
        f_green = X_reshaped[:, :, 0]
        f_cool = X_reshaped[:, :, 1]
        f_blue = X_reshaped[:, :, 2]

        # Initialize output objectives
        F_obj = np.zeros((pop_size, 3))
        
        # Initialize output constraints
        G_const = np.zeros((pop_size, 51))

        # 1. Evaluate constraints
        # Area constraint: average treatment fraction <= 0.15
        mean_treatment = np.mean(f_green + f_cool + f_blue, axis=1)
        G_const[:, 0] = mean_treatment - 0.15

        # Zone constraints: sum of fractions for each zone <= 1.0
        for i in range(50):
            G_const[:, i + 1] = f_green[:, i] + f_cool[:, i] + f_blue[:, i] - 1.0

        # 2. Evaluate objectives
        for pop_idx in range(pop_size):
            # Create a copy of baseline features for modification
            # shape (50, 18)
            mod_feats = self.baseline_zone_feats.copy()

            # Denormalize NDVI, ALBEDO, and NDWI to apply intervention updates
            ndvi_raw = mod_feats[:, self.ndvi_idx] * self.stds[self.ndvi_idx] + self.means[self.ndvi_idx]
            albedo_raw = mod_feats[:, self.albedo_idx] * self.stds[self.albedo_idx] + self.means[self.albedo_idx]
            ndwi_raw = mod_feats[:, self.ndwi_idx] * self.stds[self.ndwi_idx] + self.means[self.ndwi_idx]
            built_raw = mod_feats[:, self.built_idx] * self.stds[self.built_idx] + self.means[self.built_idx]

            # Apply intervention updates:
            # 1. Urban greening: increase NDVI by 0.20
            ndvi_new = ndvi_raw + 0.20 * f_green[pop_idx]
            
            # 2. Cool roofs: increase ALBEDO by 0.45 where BUILT_SURFACE_FRACTION > 0.5
            cool_roof_mask = built_raw > 0.5
            albedo_new = albedo_raw.copy()
            albedo_new[cool_roof_mask] = albedo_raw[cool_roof_mask] + 0.45 * f_cool[pop_idx, cool_roof_mask]
            
            # 3. Blue infrastructure: set NDWI to 0.3
            ndwi_new = ndwi_raw + (0.3 - ndwi_raw) * f_blue[pop_idx]

            # Re-normalize features
            mod_feats[:, self.ndvi_idx] = (ndvi_new - self.means[self.ndvi_idx]) / self.stds[self.ndvi_idx]
            mod_feats[:, self.albedo_idx] = (albedo_new - self.means[self.albedo_idx]) / self.stds[self.albedo_idx]
            mod_feats[:, self.ndwi_idx] = (ndwi_new - self.means[self.ndwi_idx]) / self.stds[self.ndwi_idx]

            # Predict modified temperature
            pred_lst = self.xgb_model.predict(mod_feats)
            delta_t_zone = self.baseline_lst - pred_lst # positive means cooling

            # Objective 1: Maximize average cooling -> Minimize negated average cooling
            F_obj[pop_idx, 0] = -np.mean(delta_t_zone)

            # Objective 2: Minimize implementation cost
            # greening: 120 Cr per %, cool roofs: 80 Cr per %, blue infra: 40 Cr per %
            # Note: fractions are in [0, 1], so percent is fraction * 100
            cost = np.sum(
                f_green[pop_idx] * 120 * 100 +
                f_cool[pop_idx] * 80 * 100 +
                f_blue[pop_idx] * 40 * 100
            )
            F_obj[pop_idx, 1] = cost

            # Objective 3: Minimize inequity (std deviation of cooling across zones)
            F_obj[pop_idx, 2] = np.std(delta_t_zone)

        out["F"] = F_obj
        out["G"] = G_const

def compute_zone_averages(features: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """
    Divide Delhi NCR into a 5x10 spatial grid (50 zones) and calculate the
    average baseline features for each zone.
    """
    n_patches, patch_h, patch_w, n_features = features.shape
    
    lat_step = (LAT_MAX - LAT_MIN) / 5.0
    lon_step = (LON_MAX - LON_MIN) / 10.0

    # Flatten patches to pixels (N * 256 * 256, 18)
    # To keep memory usage manageable, we can map patches to zones directly
    # and compute zone averages by averaging patch features.
    zone_sums = np.zeros((50, n_features), dtype=np.float64)
    zone_counts = np.zeros(50, dtype=np.int64)

    for i in range(n_patches):
        lat, lon = centroids[i]
        lat_idx = int((lat - LAT_MIN) / lat_step)
        lon_idx = int((lon - LON_MIN) / lon_step)
        
        lat_idx = max(0, min(4, lat_idx))
        lon_idx = max(0, min(9, lon_idx))
        zone_id = lat_idx * 10 + lon_idx
        
        # Calculate mean feature vector for this patch
        patch_mean = np.mean(features[i], axis=(0, 1))
        zone_sums[zone_id] += patch_mean
        zone_counts[zone_id] += 1

    zone_averages = np.zeros((50, n_features), dtype=np.float32)
    global_mean = np.mean(features, axis=(0, 1, 2))

    for i in range(50):
        if zone_counts[i] > 0:
            zone_averages[i] = zone_sums[i] / zone_counts[i]
        else:
            # Fallback to global average if a grid cell has no patches
            zone_averages[i] = global_mean

    return zone_averages

def main():
    h5_path = DATA_PROCESSED / "delhi_tiles.h5"
    xgb_path = DATA_PROCESSED / "xgb_model.joblib"

    if not h5_path.exists() or not xgb_path.exists():
        print("ERROR: Make sure tile_to_hdf5.py and xgboost_baseline.py have run successfully.")
        print(f"HDF5 path: {h5_path.exists()}, XGBoost path: {xgb_path.exists()}")
        sys.exit(1)

    print("Loading datasets and model...")
    xgb_model = joblib.load(xgb_path)
    
    with h5py.File(h5_path, "r") as h5f:
        features = h5f["patches/features"][:]
        band_names = [n.decode("utf-8") for n in h5f["metadata/band_names"][:]]
        centroids = h5f["metadata/centroids"][:]
        means = h5f["metadata/norm_stats/means"][:]
        stds = h5f["metadata/norm_stats/stds"][:]

    # Compute baseline features per zone (5x10 grid)
    print("Computing 50-zone spatial averages...")
    baseline_zone_feats = compute_zone_averages(features, centroids)

    # Initialize optimization problem
    problem = UrbanHeatOptimizationProblem(
        xgb_model=xgb_model,
        baseline_zone_feats=baseline_zone_feats,
        band_names=band_names,
        means=means,
        stds=stds
    )

    # Generate reference directions for 3 objectives with partitions=12
    ref_dirs = get_reference_directions("das-dennis", 3, n_partitions=12)
    
    # Configure NSGA-III
    algorithm = NSGA3(
        pop_size=200,
        ref_dirs=ref_dirs
    )

    print("\nRunning NSGA-III multi-objective optimization...")
    print("  Population size: 200")
    print("  Generations: 300")
    
    res = minimize(
        problem,
        algorithm,
        termination=('n_gen', 300),
        seed=42,
        verbose=False
    )

    if res.F is None or len(res.F) == 0:
        print("ERROR: Optimization returned no solutions.")
        sys.exit(1)

    # Extract Pareto front solutions
    # Objectives returned: [negated_deltaT, cost, equity]
    pareto_solutions = []
    recommended_sol = None
    max_cooling_under_budget = -1.0

    print(f"\nFound {len(res.F)} Pareto-optimal solutions.")

    for idx in range(len(res.F)):
        sol_x = res.X[idx].reshape(50, 3)
        delta_t = -res.F[idx, 0]  # negated back to positive cooling °C
        cost = res.F[idx, 1]
        equity = res.F[idx, 2]

        green_pct = float(np.mean(sol_x[:, 0]) * 100)
        cool_pct = float(np.mean(sol_x[:, 1]) * 100)
        # 1% of Delhi NCR area is approx 1500 hectares. We can scale it or report fraction.
        # Let's save blue infra in percent as well
        blue_pct = float(np.mean(sol_x[:, 2]) * 100)

        sol_dict = {
            "solution_id": int(idx),
            "greening_pct": green_pct,
            "coolroof_pct": cool_pct,
            "blueinfra_ha": blue_pct, # storing fraction as %
            "delta_t_c": float(delta_t),
            "cost_cr": float(cost),
            "equity_score": float(equity),
            "zone_allocations": sol_x.tolist() # [50, 3] allocation matrix
        }
        pareto_solutions.append(sol_dict)

        # Recommendation rule: highest LST reduction with cost < 25000 Cr
        if cost < 25000:
            if delta_t > max_cooling_under_budget:
                max_cooling_under_budget = delta_t
                recommended_sol = sol_dict

    # Save Pareto front
    front_path = DATA_PROCESSED / "pareto_front.json"
    with open(front_path, "w") as f:
        json.dump(pareto_solutions, f, indent=2)
    print(f"Saved Pareto front to {front_path}")

    # Save Recommended strategy
    if recommended_sol is None:
        # Fallback to the lowest cost solution if all exceed budget
        recommended_sol = pareto_solutions[np.argmin([s["cost_cr"] for s in pareto_solutions])]
        print("WARNING: No solution found under budget limit of 25000 Cr. Selecting lowest cost strategy.")

    rec_path = DATA_PROCESSED / "recommended_intervention.json"
    with open(rec_path, "w") as f:
        json.dump(recommended_sol, f, indent=2)
    print(f"Saved recommended strategy to {rec_path}")

    print("\nOptimization Summary:")
    print(f"  Pareto Solutions: {len(pareto_solutions)}")
    print(f"  Recommended Strategy (ID {recommended_sol['solution_id']}):")
    print(f"    Cooling Delta : {recommended_sol['delta_t_c']:.4f}°C")
    print(f"    Est. Cost     : {recommended_sol['cost_cr']:.2f} Cr")
    print(f"    Equity Score  : {recommended_sol['equity_score']:.4f} (std deviation of cooling)")
    print(f"    Avg Greening  : {recommended_sol['greening_pct']:.2f}%")
    print(f"    Avg Cool Roof : {recommended_sol['coolroof_pct']:.2f}%")
    print(f"    Avg Blue Infra: {recommended_sol['blueinfra_ha']:.2f}%")

if __name__ == "__main__":
    main()
