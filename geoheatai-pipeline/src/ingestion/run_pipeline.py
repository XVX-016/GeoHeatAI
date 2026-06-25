"""
GeoHeatAI — Phase 1 pipeline orchestrator.

Ties together landsat_lst, sentinel2_indices, era5_alignment, and
urban_morphology into one aligned per-scene feature stack, then exports
each scene as a GeoTIFF (via GEE's export-to-Drive) ready for the HDF5
tiling step that feeds the ML models in Phase 2/3.

Why export-to-Drive instead of pulling pixels directly via getInfo()/
sampleRectangle(): GEE's synchronous pixel-fetch methods are capped at a
few thousand pixels per request, which is far too small for a 30m grid
over the full Delhi NCR bounding box (~30,000 x 27,000m -> ~1000x900 px
per band, multiplied by ~15 bands). Export-to-Drive runs server-side as a
batch task and produces full-resolution GeoTIFFs without that limit -
this is the standard GEE pattern for anything beyond toy-sized regions.

Each Landsat scene becomes one export task. Expect this to take a while
for hundreds of scenes - GEE batch tasks queue and run asynchronously on
Google's backend, not on your machine, so it's safe to kick off a large
batch and check back later.
"""

import sys
import time
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import (
    CITY_BOUNDS,
    DEFAULT_CITY,
    EXPORT_FOLDER_DRIVE,
    SUMMER_MONTHS,
    TARGET_RESOLUTION_M,
)
from src.ingestion.era5_alignment import align_landsat_era5
from src.ingestion.landsat_lst import get_landsat_collection
from src.ingestion.sentinel2_indices import get_median_composite
from src.ingestion.urban_morphology import compute_svf_proxy, get_ghsl_morphology


def build_static_layer_stack(city: str = DEFAULT_CITY) -> ee.Image:
    """
    Build the time-invariant feature stack: NDVI/NDBI/NDWI/albedo (as a
    cloud-free median composite, since these change slowly relative to
    LST) + GHSL building height/density + SVF proxy.

    This stack gets attached to EVERY Landsat scene identically, since
    re-running cloud masking/compositing per-scene for these slow-changing
    layers would be wasteful and noisier than a clean seasonal composite.
    """
    s2_composite = get_median_composite(city=city, months=SUMMER_MONTHS)
    s2_features = s2_composite.select(["NDVI", "NDBI", "NDWI", "ALBEDO"])

    ghsl = get_ghsl_morphology(city=city)
    svf = compute_svf_proxy(ghsl)

    return s2_features.addBands(ghsl).addBands(svf)


def build_scene_feature_stack(
    landsat_image: ee.Image, static_stack: ee.Image, city: str = DEFAULT_CITY
) -> ee.Image:
    """
    For a single Landsat scene: attach ERA5 meteorological bands (temporally
    aligned to this exact overpass) and the static morphology/vegetation
    stack, reprojected to match this scene's grid.

    Returns one ee.Image with every Phase-1 band the ML stages need:
    LST_C, SR_B2-7 (Landsat reflectance), AIR_TEMP_C, RELATIVE_HUMIDITY_PCT,
    WIND_SPEED_MS, SURFACE_PRESSURE_PA, NET_SOLAR_RAD_J, NDVI, NDBI, NDWI,
    ALBEDO, BUILDING_HEIGHT_M, BUILT_SURFACE_FRACTION, SVF_PROXY.
    """
    with_era5 = align_landsat_era5(landsat_image, city=city)

    static_reprojected = static_stack.resample("bilinear").reproject(
        crs=landsat_image.select(0).projection(), scale=TARGET_RESOLUTION_M
    )

    return with_era5.addBands(static_reprojected)


def export_scene_to_drive(
    feature_stack: ee.Image, scene_id: str, city: str = DEFAULT_CITY
) -> ee.batch.Task:
    """
    Kick off an asynchronous GEE export task for one fully-assembled scene.
    Writes a multi-band GeoTIFF to Google Drive under EXPORT_FOLDER_DRIVE.
    Returns the Task object so the caller can track status if desired.
    """
    bbox = CITY_BOUNDS[city]["bbox"]
    region = ee.Geometry.Rectangle(bbox)

    task = ee.batch.Export.image.toDrive(
        image=feature_stack.clip(region),
        description=f"geoheatai_{city}_{scene_id}",
        folder=EXPORT_FOLDER_DRIVE,
        fileNamePrefix=f"geoheatai_{city}_{scene_id}",
        region=region,
        scale=TARGET_RESOLUTION_M,
        crs=CITY_BOUNDS[city]["utm_epsg"],
        maxPixels=1e10,
        fileFormat="GeoTIFF",
    )
    task.start()
    return task


def run_phase1_export(
    city: str = DEFAULT_CITY, max_scenes: int | None = None, dry_run: bool = True
) -> list:
    """
    Top-level entry point. Builds the static layer stack once, iterates
    over available Landsat scenes, assembles each per-scene feature stack,
    and either:
      - dry_run=True: just lists what WOULD be exported (scene IDs + dates),
        with zero GEE export quota consumed. Use this first to sanity check
        scene count and dates before committing to a real export batch.
      - dry_run=False: actually kicks off export tasks for up to max_scenes.

    Returns the list of started ee.batch.Task objects (empty if dry_run).
    """
    landsat_coll = get_landsat_collection(city=city, months=SUMMER_MONTHS)
    scene_list = landsat_coll.toList(landsat_coll.size())
    total_scenes = scene_list.size().getInfo()
    n_scenes = total_scenes

    if max_scenes:
        n_scenes = min(n_scenes, max_scenes)

    print(
        f"Found {total_scenes} Landsat scenes for {city} "
        f"(summer months {SUMMER_MONTHS})."
    )
    if max_scenes:
        print(f"Previewing first {n_scenes} scenes because max_scenes={max_scenes}.")

    if dry_run:
        print("DRY RUN — listing scene dates only, no export tasks started.\n")
        for i in range(n_scenes):
            img = ee.Image(scene_list.get(i))
            date_str = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd").getInfo()
            scene_id = img.get("system:index").getInfo()
            print(f"  [{i+1}/{n_scenes}] {date_str}  ({scene_id})")
        return []

    static_stack = build_static_layer_stack(city=city)
    tasks = []

    for i in range(n_scenes):
        img = ee.Image(scene_list.get(i))
        scene_id = img.get("system:index").getInfo()

        feature_stack = build_scene_feature_stack(img, static_stack, city=city)
        task = export_scene_to_drive(feature_stack, scene_id, city=city)
        tasks.append(task)

        print(f"  [{i+1}/{n_scenes}] export started: {scene_id} (task id: {task.id})")
        time.sleep(0.5)  # gentle pacing against GEE task-submission rate limits

    print(f"\n{len(tasks)} export tasks submitted. Monitor progress at:")
    print("  https://code.earthengine.google.com/tasks")
    return tasks


if __name__ == "__main__":
    from src.utils.gee_auth import init_with_service_account

    init_with_service_account()

    # ALWAYS dry-run first to sanity check before spending export quota.
    # run_phase1_export(dry_run=True, max_scenes=None)

    # Once the scene list/dates look right, flip dry_run=False to actually export:
    run_phase1_export(dry_run=False, max_scenes=None)
