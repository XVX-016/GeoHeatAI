"""
GeoHeatAI — Direct Local Download of GEE scenes (no cloud storage required).

Divides the target city bounding box into small tiles, downloads each tile
as a zip via getDownloadURL, extracts the GeoTIFF, merges them locally
using rasterio.merge.merge, and saves the final scene to data/raw.
"""

import sys
import time
import zipfile
import io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
import rasterio
from rasterio.merge import merge
import ee

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.config import DATA_RAW, TILES_TEMP_DIR, CITY_BOUNDS, DEFAULT_CITY, SUMMER_MONTHS
from src.ingestion.landsat_lst import get_landsat_collection
from src.ingestion.run_pipeline import build_static_layer_stack, build_scene_feature_stack

# Constants
DELHI_BBOX = CITY_BOUNDS["delhi_ncr"]["bbox"]  # [west, south, east, north]
TILE_DEGREES = 0.08  # ~8km tiles at Delhi latitude to stay under 32MB limit

TARGET_BANDS = [
    "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7",
    "LST_C", "AIR_TEMP_C", "RELATIVE_HUMIDITY_PCT", "WIND_SPEED_MS",
    "SURFACE_PRESSURE_PA", "NET_SOLAR_RAD_J",
    "NDVI", "NDBI", "NDWI", "ALBEDO",
    "BUILDING_HEIGHT_M", "BUILT_SURFACE_FRACTION", "SVF_PROXY"
]

# Static stack caching
_STATIC_STACK_CACHE = {}

def generate_tiles(bbox: list[float], tile_degrees: float) -> list[dict]:
    """
    Generates a grid of tile coordinate dicts covering the bbox.
    Overlap tiles by 0.005 degrees to avoid edge artifacts.
    """
    west_min, south_min, east_max, north_max = bbox
    tiles = []
    
    # Effectively smaller step to create overlap
    step = tile_degrees - 0.005
    
    col = 0
    lon = west_min
    while lon < east_max:
        row = 0
        lat = south_min
        while lat < north_max:
            tile_west = lon
            tile_east = min(lon + tile_degrees, east_max)
            tile_south = lat
            tile_north = min(lat + tile_degrees, north_max)
            
            tiles.append({
                "west": tile_west,
                "south": tile_south,
                "east": tile_east,
                "north": tile_north,
                "col": col,
                "row": row
            })
            lat += step
            row += 1
        lon += step
        col += 1
        
    return tiles

def download_scene_tile(
    image: ee.Image, tile: dict, scene_id: str, 
    tile_idx: int, out_dir: Path
) -> Path | None:
    """
    Downloads one tile of one scene as a zip via getDownloadURL, extracts the GeoTIFF,
    and saves to out_dir / f"{scene_id}_tile_{tile_idx}.tif".
    """
    dest_path = out_dir / f"{scene_id}_tile_{tile_idx}.tif"
    
    # If file already exists and is non-empty, skip download
    if dest_path.exists() and dest_path.stat().st_size > 10000:
        return dest_path
        
    region = ee.Geometry.Rectangle([tile["west"], tile["south"], tile["east"], tile["north"]])
    
    try:
        url = image.getDownloadURL({
            'name': f"{scene_id}_tile_{tile_idx}",
            'bands': TARGET_BANDS,
            'region': region,
            'scale': 30,
            'crs': 'EPSG:32643',
            'format': 'GEO_TIFF',
            'filePerBand': False
        })
        
        # Download zip file content
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        
        # GEE returns the raw multi-band GeoTIFF directly, not a zip
        dest_path.write_bytes(resp.content)
        return dest_path
    except Exception as e:
        print(f"Warning: Failed to download tile {tile_idx} for scene {scene_id}: {e}")
        return None

def merge_scene_tiles(
    tile_paths: list[Path], scene_id: str, out_dir: Path
) -> Path:
    """
    Mosaics all tile GeoTIFFs for one scene into a single file:
    out_dir / f"geoheatai_delhi_ncr_{scene_id}.tif", then deletes individual tiles.
    """
    src_files = [rasterio.open(p) for p in tile_paths]
    
    # Merge datasets
    mosaic, out_trans = merge(src_files)
    
    # Prepare output metadata
    out_meta = src_files[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans
    })
    
    merged_path = out_dir / f"geoheatai_delhi_ncr_{scene_id}.tif"
    with rasterio.open(merged_path, "w", **out_meta) as dest:
        dest.write(mosaic)
        
    # Close resources
    for src in src_files:
        src.close()
        
    # Clean up individual tile files
    for p in tile_paths:
        try:
            p.unlink()
        except Exception:
            pass
            
    return merged_path

def download_scene(
    image: ee.Image, scene_id: str,
    tiles: list[dict], out_dir: Path,
    max_workers: int = 4
) -> Path | None:
    """
    Downloads all tiles for one scene in parallel, mosaics them, and returns merged path.
    """
    temp_dir = TILES_TEMP_DIR / scene_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    tile_paths = []
    
    # Download tiles in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(download_scene_tile, image, tile, scene_id, idx, temp_dir)
            for idx, tile in enumerate(tiles)
        ]
        
        for fut in futures:
            res = fut.result()
            if res is not None:
                tile_paths.append(res)
                
    success_pct = len(tile_paths) / len(tiles)
    if success_pct < 0.70:
        print(f"Warning: Only {success_pct:.1%} of tiles succeeded for scene {scene_id}. Skipping merge.")
        return None
        
    # Merge and delete temp folder
    merged_file = merge_scene_tiles(tile_paths, scene_id, out_dir)
    
    # Remove temp folder
    try:
        temp_dir.rmdir()
    except Exception:
        pass
        
    return merged_file

def build_full_scene_image(
    landsat_image: ee.Image, city: str = "delhi_ncr"
) -> tuple[ee.Image, str]:
    """
    Assembles the full multi-band scene image with aligned ERA5 and static morphology variables.
    """
    if city not in _STATIC_STACK_CACHE:
        _STATIC_STACK_CACHE[city] = build_static_layer_stack(city=city)
        
    static_stack = _STATIC_STACK_CACHE[city]
    
    # Build stack and select target bands in order
    full_image = build_scene_feature_stack(landsat_image, static_stack, city=city)
    full_image = full_image.select(TARGET_BANDS)
    
    scene_id_string = landsat_image.get("system:index").getInfo()
    return full_image, scene_id_string

def download_all_scenes(
    out_dir: Path = DATA_RAW,
    max_scenes: int | None = None,
    resume: bool = True
) -> list[Path]:
    """
    Queries Landsat, slices/downloads all tiles per scene, and merges them to out_dir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    TILES_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Querying Landsat 8+9 collections from GEE...")
    landsat_coll = get_landsat_collection(city=DEFAULT_CITY, months=SUMMER_MONTHS)
    scene_list = landsat_coll.toList(landsat_coll.size())
    total_scenes = scene_list.size().getInfo()
    
    n_scenes = total_scenes if max_scenes is None else min(total_scenes, max_scenes)
    print(f"Found {total_scenes} summer scenes. Slicing to process {n_scenes} scenes.")
    
    tiles = generate_tiles(DELHI_BBOX, TILE_DEGREES)
    print(f"Generated {len(tiles)} tiles of size {TILE_DEGREES} degrees per scene.")
    
    downloaded_paths = []
    
    for i in range(n_scenes):
        img = ee.Image(scene_list.get(i))
        scene_id = img.get("system:index").getInfo()
        
        # Strip merge indexes if present to clean scene name for output file
        import re
        match = re.search(r'(LC0[89]_[0-9]+_[0-9]+)', scene_id)
        file_scene_id = match.group(1) if match else scene_id
        
        merged_filename = out_dir / f"geoheatai_delhi_ncr_{file_scene_id}.tif"
        
        if resume and merged_filename.exists() and merged_filename.stat().st_size > 1000000:
            print(f"Scene {i+1}/{n_scenes}: {file_scene_id} already downloaded. Skipping.")
            downloaded_paths.append(merged_filename)
            continue
            
        print(f"\nScene {i+1}/{n_scenes}: {file_scene_id} — Starting download of {len(tiles)} tiles...")
        
        # Build image stack and download
        full_image, _ = build_full_scene_image(img, DEFAULT_CITY)
        merged_path = download_scene(full_image, file_scene_id, tiles, out_dir, max_workers=4)
        
        if merged_path:
            downloaded_paths.append(merged_path)
            print(f"Scene {i+1}/{n_scenes}: {file_scene_id} complete. Merged to {merged_path}")
        else:
            print(f"Scene {i+1}/{n_scenes}: {file_scene_id} failed.")
            
        # Pacing
        time.sleep(1.0)
        
    print(f"\nDownloaded and merged {len(downloaded_paths)} of {n_scenes} successfully.")
    return downloaded_paths

if __name__ == "__main__":
    from src.utils.gee_auth import init_with_service_account
    init_with_service_account()
    
    print("Starting direct local download process...")
    paths = download_all_scenes(max_scenes=None, resume=True)
    print(f"Download complete: {len(paths)} scenes saved in {DATA_RAW}")
