"""
GeoHeatAI — Landsat 8/9 Land Surface Temperature ingestion.

Pulls Collection 2 Level-2 surface temperature product (already
atmospherically corrected by USGS), applies cloud/shadow/snow masking via
the QA_PIXEL band, and converts the raw thermal band to Celsius.

Landsat C2 L2 ST_B10 is delivered as a scaled integer:
    LST (Kelvin) = ST_B10 * 0.00341802 + 149.0
We convert to Celsius for downstream use since that's the unit every
consumer (frontend, SHAP, optimizer) expects.
"""

import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import (
    CITY_BOUNDS,
    CLOUD_COVER_MAX_PCT,
    COLLECTIONS,
    DEFAULT_CITY,
    END_DATE,
    START_DATE,
)

# QA_PIXEL bit flags for Landsat Collection 2 (USGS spec)
QA_BIT_DILATED_CLOUD = 1
QA_BIT_CIRRUS = 2
QA_BIT_CLOUD = 3
QA_BIT_CLOUD_SHADOW = 4
QA_BIT_SNOW = 5


def mask_landsat_qa(image: ee.Image) -> ee.Image:
    """
    Apply cloud/shadow/cirrus/snow masking using QA_PIXEL bit flags.
    Also masks saturated pixels via QA_RADSAT.
    """
    qa = image.select("QA_PIXEL")

    cloud_mask = (
        qa.bitwiseAnd(1 << QA_BIT_DILATED_CLOUD)
        .eq(0)
        .And(qa.bitwiseAnd(1 << QA_BIT_CIRRUS).eq(0))
        .And(qa.bitwiseAnd(1 << QA_BIT_CLOUD).eq(0))
        .And(qa.bitwiseAnd(1 << QA_BIT_CLOUD_SHADOW).eq(0))
        .And(qa.bitwiseAnd(1 << QA_BIT_SNOW).eq(0))
    )

    saturation_mask = image.select("QA_RADSAT").eq(0)

    return image.updateMask(cloud_mask).updateMask(saturation_mask)


def scale_landsat_bands(image: ee.Image) -> ee.Image:
    """
    Apply USGS-specified scale factors to convert raw DN to physical units.
    Optical SR bands -> reflectance [0,1]. Thermal ST band -> Kelvin, then
    we convert to Celsius and rename to LST_C for clarity downstream.
    """
    optical_bands = image.select("SR_B.").multiply(0.0000275).add(-0.2)

    thermal_kelvin = image.select("ST_B10").multiply(0.00341802).add(149.0)
    thermal_celsius = thermal_kelvin.subtract(273.15).rename("LST_C")

    return image.addBands(optical_bands, overwrite=True).addBands(
        thermal_celsius, overwrite=True
    )


def get_landsat_collection(
    city: str = DEFAULT_CITY,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    months: list[int] | None = None,
) -> ee.ImageCollection:
    """
    Build a merged, masked, scaled Landsat 8+9 collection over the target
    city for the given date range, optionally filtered to specific months
    (e.g. [3,4,5,6] for pre-monsoon summer in Delhi).

    Returns an ImageCollection where each image carries SR_B* (reflectance)
    and LST_C (surface temperature in Celsius) bands, cloud-masked.
    """
    bbox = CITY_BOUNDS[city]["bbox"]
    region = ee.Geometry.Rectangle(bbox)

    def build(collection_id: str) -> ee.ImageCollection:
        coll = (
            ee.ImageCollection(collection_id)
            .filterBounds(region)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUD_COVER", CLOUD_COVER_MAX_PCT))
            .map(mask_landsat_qa)
            .map(scale_landsat_bands)
        )
        if months:
            coll = coll.filter(ee.Filter.calendarRange(months[0], months[-1], "month"))
        return coll

    l8 = build(COLLECTIONS["landsat8_sr"])
    l9 = build(COLLECTIONS["landsat9_sr"])

    return l8.merge(l9).sort("system:time_start")


def get_scene_count(city: str = DEFAULT_CITY, **kwargs) -> int:
    """Quick sanity check — how many clear(ish) scenes are available."""
    coll = get_landsat_collection(city=city, **kwargs)
    return coll.size().getInfo()


if __name__ == "__main__":
    from src.utils.gee_auth import init_with_service_account

    init_with_service_account()
    count = get_scene_count()
    print(f"Available Landsat 8+9 scenes over Delhi NCR ({START_DATE} to {END_DATE}): {count}")
