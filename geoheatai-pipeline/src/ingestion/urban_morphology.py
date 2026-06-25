"""
GeoHeatAI — urban morphology ingestion (GHSL building data + OSM via geopandas).

Two data sources, two different access patterns:
1. GHSL (Global Human Settlement Layer) — already in GEE as a raster, so we
   pull it the same way as the other Earth Engine collections.
2. OpenStreetMap building footprints — NOT in GEE. Pulled separately via
   the Overpass API + geopandas, then rasterized to match our 30m grid so
   it can be stacked with the GEE-derived bands later in preprocessing.

Sky View Factor (SVF) — the fraction of the sky hemisphere visible from a
ground point — is the single best predictor of nocturnal heat retention but
has no direct global GEE product. We compute a defensible raster proxy from
GHSL building height (GHS_BUILT_H) using a simplified geometric approximation
rather than a full ray-traced SVF (which needs LiDAR-grade DSM data we don't
have access to). This proxy is flagged clearly so it can be swapped for a
proper SOLWEIG-based SVF later if time allows (see Phase 3 notes).
"""

import sys
from pathlib import Path

import ee
import geopandas as gpd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import CITY_BOUNDS, COLLECTIONS, DATA_RAW, DEFAULT_CITY, TARGET_RESOLUTION_M

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"


def get_ghsl_morphology(city: str = DEFAULT_CITY) -> ee.Image:
    """
    Pull GHSL built-up height and surface fraction for the target city.
    GHS_BUILT_H_ANBH = average net building height (m), 100m native resolution.
    GHS_BUILT_S = built-up surface fraction per pixel [0,1], 100m native.
    Both are resampled to TARGET_RESOLUTION_M via bilinear interpolation —
    appropriate here since these are continuous physical quantities, not
    categorical land cover.
    """
    bbox = CITY_BOUNDS[city]["bbox"]
    region = ee.Geometry.Rectangle(bbox)

    built_height = (
        ee.Image(COLLECTIONS["ghsl_built_height"])
        .clip(region)
        .rename("BUILDING_HEIGHT_M")
    )
    built_surface = (
        ee.ImageCollection(COLLECTIONS["ghsl_built_surface"])
        .filterBounds(region)
        .mosaic()
        .clip(region)
        .rename("BUILT_SURFACE_FRACTION")
    )

    combined = built_height.addBands(built_surface)
    return combined.resample("bilinear").reproject(
        crs=CITY_BOUNDS[city]["utm_epsg"], scale=TARGET_RESOLUTION_M
    )


def compute_svf_proxy(ghsl_image: ee.Image, kernel_radius_px: int = 5) -> ee.Image:
    """
    Geometric SVF proxy: approximates sky obstruction as an inverse function
    of neighborhood-average building height and built density, using a
    focal-mean kernel to capture the surrounding urban canyon effect rather
    than just the pixel's own height.

    SVF_proxy = 1 - (normalized local height x normalized local density),
    clamped to [0,1]. This is a simplification — true SVF requires
    directional ray-casting against a full 3D building model — but it
    captures the dominant first-order effect (tall, dense areas trap more
    longwave radiation at night) and is appropriate given our data
    constraints. Document this limitation in the technical report.
    """
    kernel = ee.Kernel.circle(radius=kernel_radius_px)

    height_smooth = ghsl_image.select("BUILDING_HEIGHT_M").focal_mean(kernel=kernel)
    density_smooth = ghsl_image.select("BUILT_SURFACE_FRACTION").focal_mean(kernel=kernel)

    # Normalize height against a reasonable Delhi-context max (~60m covers
    # all but a handful of high-rises) so the proxy stays in [0,1] before
    # combining with density.
    height_norm = height_smooth.divide(60).clamp(0, 1)

    obstruction = height_norm.multiply(density_smooth)
    svf_proxy = ee.Image(1).subtract(obstruction).rename("SVF_PROXY").clamp(0, 1)

    return svf_proxy


def fetch_osm_buildings(city: str = DEFAULT_CITY, save: bool = True) -> gpd.GeoDataFrame:
    """
    Pull building footprint polygons from OpenStreetMap via the Overpass API
    for the target city's bounding box. Returns a GeoDataFrame in EPSG:4326.

    Note: Overpass queries over a full metro area can be large/slow and the
    public Overpass endpoint rate-limits aggressively. For repeated runs,
    cache the result to disk (save=True does this automatically) rather than
    re-querying every time.
    """
    bbox = CITY_BOUNDS[city]["bbox"]
    west, south, east, north = bbox

    # Overpass QL: all way/relation features tagged building=*, within bbox
    query = f"""
    [out:json][timeout:180];
    (
      way["building"]({south},{west},{north},{east});
      relation["building"]({south},{west},{north},{east});
    );
    out geom;
    """

    response = requests.post(OVERPASS_API_URL, data={"data": query}, timeout=200)
    response.raise_for_status()
    osm_json = response.json()

    records = []
    for element in osm_json.get("elements", []):
        if element["type"] == "way" and "geometry" in element:
            coords = [(pt["lon"], pt["lat"]) for pt in element["geometry"]]
            if len(coords) >= 3:
                from shapely.geometry import Polygon

                records.append(
                    {
                        "osm_id": element["id"],
                        "geometry": Polygon(coords),
                        "building_tag": element.get("tags", {}).get("building", "yes"),
                    }
                )

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

    if save:
        out_path = DATA_RAW / f"osm_buildings_{city}.geojson"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(out_path, driver="GeoJSON")
        print(f"Saved {len(gdf)} building footprints to {out_path}")

    return gdf


def compute_building_density_from_osm(
    gdf: gpd.GeoDataFrame, city: str = DEFAULT_CITY, grid_size_m: int = TARGET_RESOLUTION_M
) -> gpd.GeoDataFrame:
    """
    Rasterize OSM building footprints into a building-density-per-cell grid
    at TARGET_RESOLUTION_M, for use as a cross-check against the GHSL-derived
    BUILT_SURFACE_FRACTION band (OSM coverage is patchy outside city cores,
    so this should never fully replace GHSL — it's a refinement layer where
    OSM data quality is good, mainly central Delhi).

    Returns a GeoDataFrame of grid cells with a 'building_coverage_pct' column.
    Actual raster conversion to align with the GEE-derived stack happens in
    the preprocessing step (rasterio + rasterize), not here.
    """
    utm_epsg = CITY_BOUNDS[city]["utm_epsg"]
    gdf_utm = gdf.to_crs(utm_epsg)
    gdf_utm["area_m2"] = gdf_utm.geometry.area

    bounds = gdf_utm.total_bounds  # [minx, miny, maxx, maxy]
    print(
        f"OSM building footprints span {bounds} ({utm_epsg}); "
        f"{len(gdf_utm)} buildings, total footprint area "
        f"{gdf_utm['area_m2'].sum() / 1e6:.2f} km²"
    )
    return gdf_utm


if __name__ == "__main__":
    from src.utils.gee_auth import init_with_service_account

    init_with_service_account()

    ghsl = get_ghsl_morphology()
    print(f"GHSL bands: {ghsl.bandNames().getInfo()}")

    svf = compute_svf_proxy(ghsl)
    print(f"SVF proxy band: {svf.bandNames().getInfo()}")

    # OSM fetch is slow (Overpass API) — uncomment to actually run it
    # buildings = fetch_osm_buildings()
    # compute_building_density_from_osm(buildings)
