"""
GeoHeatAI — Sentinel-2 vegetation/built-up index ingestion.

Pulls Sentinel-2 Surface Reflectance Harmonized, masks clouds using the
s2cloudless probability collection (more reliable than the legacy QA60 band
for this collection), and derives NDVI / NDBI / NDWI spectral indices used
as cooling-driver and heating-driver features.
"""

import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import CITY_BOUNDS, CLOUD_COVER_MAX_PCT, COLLECTIONS, DEFAULT_CITY, END_DATE, START_DATE

S2_CLOUD_PROB_COLLECTION = "COPERNICUS/S2_CLOUD_PROBABILITY"
CLOUD_PROB_THRESHOLD = 40  # mask pixels with >40% cloud probability


def add_cloud_probability(image: ee.Image) -> ee.Image:
    """Join cloud probability band onto the SR image via system:index."""
    cloud_prob = ee.Image(image.get("s2cloudless")).select("probability")
    is_cloud = cloud_prob.gt(CLOUD_PROB_THRESHOLD).rename("clouds")
    return image.addBands(is_cloud)


def mask_s2_clouds(image: ee.Image) -> ee.Image:
    cloud_mask = image.select("clouds").eq(0)
    return image.updateMask(cloud_mask)


def add_spectral_indices(image: ee.Image) -> ee.Image:
    """
    NDVI  = (NIR - Red) / (NIR + Red)              -> vegetation health/density
    NDBI  = (SWIR1 - NIR) / (SWIR1 + NIR)           -> built-up surface index
    NDWI  = (Green - NIR) / (Green + NIR)           -> surface water/moisture
    Sentinel-2 band map: B2=Blue, B3=Green, B4=Red, B8=NIR, B11=SWIR1
    """
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndbi = image.normalizedDifference(["B11", "B8"]).rename("NDBI")
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")

    # Simple broadband albedo proxy (Liang 2001 coefficients, simplified for S2)
    albedo = (
        image.select("B2").multiply(0.356)
        .add(image.select("B4").multiply(0.130))
        .add(image.select("B8").multiply(0.373))
        .add(image.select("B11").multiply(0.085))
        .add(image.select("B12").multiply(0.072))
        .subtract(0.0018)
        .rename("ALBEDO")
    )

    return image.addBands([ndvi, ndbi, ndwi, albedo])


def get_sentinel2_collection(
    city: str = DEFAULT_CITY,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    months: list[int] | None = None,
) -> ee.ImageCollection:
    """
    Build a cloud-masked Sentinel-2 collection with NDVI/NDBI/NDWI/albedo
    bands attached, over the target city.
    """
    bbox = CITY_BOUNDS[city]["bbox"]
    region = ee.Geometry.Rectangle(bbox)

    s2_sr = (
        ee.ImageCollection(COLLECTIONS["sentinel2_sr"])
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUD_COVER_MAX_PCT))
    )
    s2_clouds = (
        ee.ImageCollection(S2_CLOUD_PROB_COLLECTION)
        .filterBounds(region)
        .filterDate(start_date, end_date)
    )

    joined = ee.Join.saveFirst("s2cloudless").apply(
        primary=s2_sr,
        secondary=s2_clouds,
        condition=ee.Filter.equals(
            leftField="system:index", rightField="system:index"
        ),
    )

    coll = (
        ee.ImageCollection(joined)
        .map(add_cloud_probability)
        .map(mask_s2_clouds)
        .map(add_spectral_indices)
    )

    if months:
        coll = coll.filter(ee.Filter.calendarRange(months[0], months[-1], "month"))

    return coll.sort("system:time_start")


def get_median_composite(city: str = DEFAULT_CITY, **kwargs) -> ee.Image:
    """
    A cloud-free median composite — useful for the static LULC/morphology
    feature layers that don't need per-scene temporal alignment (unlike LST,
    which must stay tied to individual Landsat overpass timestamps).
    """
    coll = get_sentinel2_collection(city=city, **kwargs)
    return coll.median()


if __name__ == "__main__":
    from src.utils.gee_auth import init_with_service_account

    init_with_service_account()
    coll = get_sentinel2_collection()
    print(f"Available Sentinel-2 scenes over Delhi NCR: {coll.size().getInfo()}")
