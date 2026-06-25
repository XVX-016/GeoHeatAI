"""
GeoHeatAI — ERA5-Land meteorological ingestion + temporal alignment.

This is the trickiest part of Phase 1: Landsat gives you sparse instantaneous
snapshots (one scene per ~16 days), while ERA5-Land gives hourly atmospheric
data at 0.1° (~9km) resolution. The correct approach is NOT to build a
continuous joined time series — it's to treat every Landsat overpass as an
independent labeled sample, and pull the single nearest ERA5 hourly composite
(within a tolerance window) for that exact moment.

Strategy implemented here:
1. For a given Landsat image's acquisition timestamp, find the ERA5-Land
   image within +/- ERA5_TIME_WINDOW_HOURS of the overpass.
2. ERA5-Land's native grid (~9km) is far coarser than our 30m target, so we
   resample using bilinear interpolation when reprojecting — this is
   defensible because atmospheric variables (air temp, humidity, wind) vary
   smoothly in space, unlike land surface properties.
3. If no ERA5 image falls within the tolerance window (rare, but possible
   near collection boundaries), the function returns None and the caller
   should skip that Landsat scene rather than fabricate a value.
"""

import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import (
    CITY_BOUNDS,
    COLLECTIONS,
    DEFAULT_CITY,
    ERA5_TIME_WINDOW_HOURS,
    TARGET_RESOLUTION_M,
)

# ERA5-Land hourly bands we care about, renamed to clear short codes
ERA5_BAND_MAP = {
    "temperature_2m": "AIR_TEMP_K",
    "dewpoint_temperature_2m": "DEWPOINT_K",
    "u_component_of_wind_10m": "WIND_U",
    "v_component_of_wind_10m": "WIND_V",
    "surface_pressure": "SURFACE_PRESSURE_PA",
    "surface_net_solar_radiation": "NET_SOLAR_RAD_J",
}


def get_era5_for_timestamp(
    timestamp_ms: ee.Number, city: str = DEFAULT_CITY
) -> ee.Image | None:
    """
    Return the ERA5-Land hourly image nearest to `timestamp_ms` (a GEE
    server-side millisecond timestamp), restricted to within
    ERA5_TIME_WINDOW_HOURS. Bands are renamed and wind components combined
    into scalar speed + derived relative humidity.

    Returns an ee.Image, or None (client-side) if nothing matched — caller
    must call .size().getInfo() to check before relying on this in a
    server-side .map() context; see align_landsat_era5() for the safe
    per-scene pattern.
    """
    window_ms = ERA5_TIME_WINDOW_HOURS * 60 * 60 * 1000
    start = ee.Date(timestamp_ms).advance(-ERA5_TIME_WINDOW_HOURS, "hour")
    end = ee.Date(timestamp_ms).advance(ERA5_TIME_WINDOW_HOURS, "hour")

    bbox = CITY_BOUNDS[city]["bbox"]
    region = ee.Geometry.Rectangle(bbox)

    candidates = (
        ee.ImageCollection(COLLECTIONS["era5_hourly"])
        .filterBounds(region)
        .filterDate(start, end)
        .select(list(ERA5_BAND_MAP.keys()), list(ERA5_BAND_MAP.values()))
    )

    # Pick the single closest-in-time image rather than averaging the window,
    # since averaging would smooth out a real diurnal swing right at the
    # overpass moment.
    def add_time_diff(img):
        diff = ee.Number(img.get("system:time_start")).subtract(timestamp_ms).abs()
        return img.set("time_diff", diff)

    sorted_candidates = candidates.map(add_time_diff).sort("time_diff")
    nearest = sorted_candidates.first()
    return nearest


def derive_relative_humidity(era5_image: ee.Image) -> ee.Image:
    """
    ERA5-Land doesn't give RH directly — derive it from air temp + dewpoint
    using the Magnus-Tetens approximation, computed in Celsius.
        RH = 100 * exp((17.625*Td)/(243.04+Td)) / exp((17.625*T)/(243.04+T))
    """
    t_c = era5_image.select("AIR_TEMP_K").subtract(273.15)
    td_c = era5_image.select("DEWPOINT_K").subtract(273.15)

    numerator = t_c.expression(
        "exp((17.625 * Td) / (243.04 + Td))", {"Td": td_c}
    )
    denominator = t_c.expression(
        "exp((17.625 * T) / (243.04 + T))", {"T": t_c}
    )
    rh = numerator.divide(denominator).multiply(100).rename("RELATIVE_HUMIDITY_PCT")

    wind_speed = (
        era5_image.select("WIND_U")
        .hypot(era5_image.select("WIND_V"))
        .rename("WIND_SPEED_MS")
    )

    return era5_image.addBands([rh, wind_speed, t_c.rename("AIR_TEMP_C")])


def align_landsat_era5(landsat_image: ee.Image, city: str = DEFAULT_CITY) -> ee.Image:
    """
    Given a single (already cloud-masked) Landsat image, attach the nearest
    ERA5-Land meteorological bands, resampled to TARGET_RESOLUTION_M via
    bilinear interpolation, and clipped/reprojected to match the Landsat
    image's footprint.

    This is the function you map over a Landsat ImageCollection to build
    the full Phase-1 aligned dataset. Designed to be called inside
    .map(), so it stays fully server-side (no .getInfo() calls).
    """
    timestamp = landsat_image.get("system:time_start")
    era5_raw = get_era5_for_timestamp(ee.Number(timestamp), city=city)
    era5_derived = derive_relative_humidity(ee.Image(era5_raw))

    era5_resampled = (
        era5_derived.resample("bilinear")
        .reproject(crs=landsat_image.select(0).projection(), scale=TARGET_RESOLUTION_M)
    )

    return landsat_image.addBands(era5_resampled)


if __name__ == "__main__":
    from src.ingestion.landsat_lst import get_landsat_collection
    from src.utils.gee_auth import init_with_service_account

    init_with_service_account()

    landsat_coll = get_landsat_collection()
    first_scene = ee.Image(landsat_coll.first())

    aligned = align_landsat_era5(first_scene)
    band_names = aligned.bandNames().getInfo()
    print(f"Aligned scene band names: {band_names}")

    acquisition_time = ee.Date(first_scene.get("system:time_start")).format().getInfo()
    print(f"Landsat acquisition timestamp: {acquisition_time}")
