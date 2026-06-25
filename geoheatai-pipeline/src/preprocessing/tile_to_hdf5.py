"""
GeoHeatAI — Spatial tiling of GeoTIFFs into HDF5 patches.

Slices multi-band GeoTIFF scenes from data/raw into 256x256 pixel patches with
32px overlap, normalizes the feature bands to Z-score using per-band statistics
computed over the entire dataset, and saves them to data/processed/delhi_tiles.h5.
"""

import os
import sys
import re
from pathlib import Path
import numpy as np
import rasterio
import h5py
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import DATA_RAW, DATA_PROCESSED, DEFAULT_CITY, CITY_BOUNDS

# Target city coordinates for projection
CITY = DEFAULT_CITY
UTM_EPSG = CITY_BOUNDS[CITY]["utm_epsg"]

# List of 19 bands expected in the GeoTIFF in order
BAND_NAMES = [
    "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7",
    "LST_C",
    "AIR_TEMP_C", "RELATIVE_HUMIDITY_PCT", "WIND_SPEED_MS", "SURFACE_PRESSURE_PA", "NET_SOLAR_RAD_J",
    "NDVI", "NDBI", "NDWI", "ALBEDO",
    "BUILDING_HEIGHT_M", "BUILT_SURFACE_FRACTION", "SVF_PROXY"
]

LST_BAND_INDEX = 6  # 0-based index of LST_C

def get_feature_and_label_indices():
    """Separate LST_C index from feature indices."""
    feature_indices = [i for i in range(len(BAND_NAMES)) if i != LST_BAND_INDEX]
    feature_names = [BAND_NAMES[i] for i in feature_indices]
    return feature_indices, LST_BAND_INDEX, feature_names

def compute_dataset_stats(tif_paths: list[Path], num_bands: int):
    """
    Calculate the mean and standard deviation for each band across the entire
    dataset, excluding NaN and nodata values, in a memory-efficient manner.
    """
    print("Pass 1: Computing per-band statistics over all scenes...")
    band_sums = np.zeros(num_bands, dtype=np.float64)
    band_sq_sums = np.zeros(num_bands, dtype=np.float64)
    band_counts = np.zeros(num_bands, dtype=np.int64)

    for i, path in enumerate(tif_paths):
        print(f"  [{i+1}/{len(tif_paths)}] Reading {path.name}...")
        with rasterio.open(path) as src:
            data = src.read()  # shape (num_bands, height, width)
            for b in range(num_bands):
                band_data = data[b]
                valid_mask = ~np.isnan(band_data)
                if src.nodata is not None:
                    valid_mask &= (band_data != src.nodata)
                
                valid_pixels = band_data[valid_mask]
                if len(valid_pixels) > 0:
                    band_sums[b] += np.sum(valid_pixels)
                    band_sq_sums[b] += np.sum(valid_pixels ** 2)
                    band_counts[b] += len(valid_pixels)

    means = np.zeros(num_bands, dtype=np.float32)
    stds = np.ones(num_bands, dtype=np.float32)

    for b in range(num_bands):
        if band_counts[b] > 0:
            means[b] = band_sums[b] / band_counts[b]
            variance = (band_sq_sums[b] / band_counts[b]) - (means[b] ** 2)
            stds[b] = np.sqrt(max(variance, 1e-10))
        print(f"  Band {BAND_NAMES[b]}: mean={means[b]:.4f}, std={stds[b]:.4f}")

    return means, stds

def extract_scene_id(filename: str) -> str:
    """Extract standard scene ID from TIFF filename."""
    # Example filename: geoheatai_delhi_ncr_1_LC08_146040_20190311.tif
    # We want to extract '1_LC08_146040_20190311' or fall back to name stem
    match = re.search(r"geoheatai_[a-zA-Z0-9_]+_([0-9]_[A-Z0-9_]+)$", Path(filename).stem)
    if match:
        return match.group(1)
    return Path(filename).stem

def slice_and_process(
    tif_paths: list[Path],
    means: np.ndarray,
    stds: np.ndarray,
    patch_size: int = 256,
    overlap: int = 32,
    max_nan_pct: float = 0.20
):
    """
    Pass 2: Slice GeoTIFFs into overlapping patches, normalize features,
    and accumulate valid patches.
    """
    print("\nPass 2: Slicing GeoTIFFs into patches...")
    stride = patch_size - overlap
    
    feature_indices, lst_index, feature_names = get_feature_and_label_indices()
    num_features = len(feature_indices)

    all_features = []
    all_labels = []
    all_scene_ids = []
    all_centroids = []

    # Projection transformer from UTM to Lat/Lon for centroids
    transformer = Transformer.from_crs(UTM_EPSG, "EPSG:4326", always_xy=True)

    for i, path in enumerate(tif_paths):
        scene_id = extract_scene_id(path.name)
        print(f"  [{i+1}/{len(tif_paths)}] Slicing {path.name} (scene_id: {scene_id})...")

        with rasterio.open(path) as src:
            data = src.read()  # (num_bands, height, width)
            transform = src.transform
            _, height, width = data.shape

            if height < patch_size or width < patch_size:
                print(f"    Skipping: dimensions too small ({width}x{height})")
                continue

            scene_patches_added = 0

            # Slide extraction window
            for y in range(0, height - patch_size + 1, stride):
                for x in range(0, width - patch_size + 1, stride):
                    patch = data[:, y:y+patch_size, x:x+patch_size]

                    # Check for NaNs or nodata values in the patch
                    # We consider a pixel invalid if it is NaN in any band
                    invalid_mask = np.isnan(patch).any(axis=0)
                    if src.nodata is not None:
                        invalid_mask |= (patch == src.nodata).any(axis=0)

                    nan_fraction = np.mean(invalid_mask)
                    if nan_fraction > max_nan_pct:
                        continue

                    # Extract labels (LST_C) and features separately
                    label_patch = patch[lst_index:lst_index+1, :, :]  # (1, 256, 256)
                    feat_patch = patch[feature_indices, :, :]  # (18, 256, 256)

                    # Normalize only features (keep LST in original Celsius)
                    # We normalize using the computed mean/std per band
                    f_means = means[feature_indices][:, None, None]
                    f_stds = stds[feature_indices][:, None, None]
                    
                    # Fill NaNs with 0 (mean) after standardization for robustness
                    feat_patch_norm = (feat_patch - f_means) / f_stds
                    feat_patch_norm[np.isnan(feat_patch_norm)] = 0.0

                    # For labels, replace NaNs with the overall mean LST as a fallback
                    label_patch_filled = label_patch.copy()
                    label_patch_filled[np.isnan(label_patch_filled)] = means[lst_index]

                    # Calculate spatial centroid coordinate
                    c_y, c_x = y + patch_size // 2, x + patch_size // 2
                    east, north = rasterio.transform.xy(transform, c_y, c_x)
                    lon, lat = transformer.transform(east, north)

                    # Store patches in HDF5 order: (256, 256, num_channels)
                    all_features.append(feat_patch_norm.transpose(1, 2, 0))
                    all_labels.append(label_patch_filled.transpose(1, 2, 0))
                    all_scene_ids.append(scene_id)
                    all_centroids.append([lat, lon])
                    scene_patches_added += 1

            print(f"    Extracted {scene_patches_added} valid patches")

    if len(all_features) == 0:
        raise ValueError("No patches were successfully extracted. Check data coordinates and quality.")

    features_arr = np.array(all_features, dtype=np.float32)
    labels_arr = np.array(all_labels, dtype=np.float32)
    centroids_arr = np.array(all_centroids, dtype=np.float32)

    return features_arr, labels_arr, centroids_arr, all_scene_ids, feature_names

def main():
    global BAND_NAMES
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    
    # Locate all GeoTIFF files exported from Google Drive
    tif_paths = sorted(list(DATA_RAW.glob("geoheatai_*.tif")))
    
    if not tif_paths:
        # Fall back to checking subfolders or any .tif
        tif_paths = sorted(list(DATA_RAW.glob("**/*.tif")))

    if not tif_paths:
        print(f"ERROR: No GeoTIFF files found in {DATA_RAW}.")
        print("Please download your Google Drive exports to data/raw/ before running.")
        sys.exit(1)

    print(f"Found {len(tif_paths)} GeoTIFF files to process.")

    # Read the number of bands from the first file
    with rasterio.open(tif_paths[0]) as r_src:
        num_bands = r_src.count
        if num_bands != len(BAND_NAMES):
            print(f"WARNING: Band count mismatch. Expected {len(BAND_NAMES)}, got {num_bands}.")
            # Adjust BAND_NAMES list dynamically if needed
            if num_bands < len(BAND_NAMES):
                BAND_NAMES = BAND_NAMES[:num_bands]
            else:
                for idx in range(len(BAND_NAMES), num_bands):
                    BAND_NAMES.append(f"BAND_{idx+1}")

    # Step 1: Compute statistics
    means, stds = compute_dataset_stats(tif_paths, num_bands)

    # Step 2: Slice and normalize
    features, labels, centroids, scene_ids, feature_names = slice_and_process(
        tif_paths, means, stds, patch_size=256, overlap=32, max_nan_pct=0.20
    )

    # Step 3: Write HDF5 file
    output_path = DATA_PROCESSED / "delhi_tiles.h5"
    print(f"\nWriting datasets to {output_path}...")
    
    feature_indices, lst_index, _ = get_feature_and_label_indices()

    with h5py.File(output_path, "w") as h5f:
        # Save patches
        h5f.create_dataset("patches/features", data=features, dtype="float32", compression="gzip")
        h5f.create_dataset("patches/labels", data=labels, dtype="float32", compression="gzip")
        
        # Save metadata
        h5f.create_dataset("metadata/band_names", data=[n.encode("utf-8") for n in feature_names])
        h5f.create_dataset("metadata/scene_ids", data=[s.encode("utf-8") for s in scene_ids])
        h5f.create_dataset("metadata/centroids", data=centroids, dtype="float32")
        
        # Save normalization statistics
        h5f.create_dataset("metadata/norm_stats/means", data=means[feature_indices], dtype="float32")
        h5f.create_dataset("metadata/norm_stats/stds", data=stds[feature_indices], dtype="float32")
        h5f.create_dataset("metadata/norm_stats/lst_mean", data=means[lst_index], dtype="float32")
        h5f.create_dataset("metadata/norm_stats/lst_std", data=stds[lst_index], dtype="float32")

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nSUCCESS: Processing complete!")
    print(f"  Total patches: {len(features)}")
    print(f"  Feature shape: {features.shape}")
    print(f"  Label shape: {labels.shape}")
    print(f"  HDF5 file size: {file_size_mb:.2f} MB")

if __name__ == "__main__":
    main()
