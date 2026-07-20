from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds

NODATA = -9999.0


def aeqd_crs(latitude_deg: float, longitude_deg: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={latitude_deg} +lon_0={longitude_deg} +datum=WGS84 +units=m +no_defs"
    )


def geographic_bbox(
    latitude_deg: float, longitude_deg: float, radius_km: float
) -> tuple[float, ...]:
    latitude_delta = radius_km / 110.574
    longitude_delta = radius_km / max(1e-6, 111.320 * math.cos(math.radians(latitude_deg)))
    return (
        longitude_deg - longitude_delta,
        latitude_deg - latitude_delta,
        longitude_deg + longitude_delta,
        latitude_deg + latitude_delta,
    )


def load_projected_grid(
    paths: list[Path],
    latitude_deg: float,
    longitude_deg: float,
    radius_km: float,
    resolution_m: float,
    *,
    categorical: bool = False,
) -> tuple[np.ndarray, rasterio.Affine, CRS]:
    """Mosaic source rasters and reproject a bounded grid around the transmitter."""

    if not paths:
        raise ValueError("at least one source raster is required")
    margin_m = max(4 * resolution_m, radius_km * 20.0)
    reach_m = radius_km * 1000.0 + margin_m
    bbox = geographic_bbox(latitude_deg, longitude_deg, (reach_m / 1000.0) * 1.02)
    sources = [rasterio.open(path) for path in paths]
    try:
        if any(source.crs != sources[0].crs for source in sources):
            raise ValueError("all source rasters must use the same CRS")
        if sources[0].crs is None:
            raise ValueError("source rasters must define a CRS")
        size = math.ceil(2 * reach_m / resolution_m)
        destination_transform = from_origin(-reach_m, reach_m, resolution_m, resolution_m)
        destination_crs = aeqd_crs(latitude_deg, longitude_deg)
        destination = np.full((size, size), NODATA, dtype="float32")

        if categorical:
            # Warp each categorical tile straight onto the common final grid. An
            # intermediate merge can manufacture one-pixel NoData seams when
            # independently cropped source tiles have slightly different grids.
            for source in sources:
                tile = np.full(destination.shape, NODATA, dtype="float32")
                reproject(
                    rasterio.band(source, 1),
                    tile,
                    src_nodata=source.nodata,
                    dst_transform=destination_transform,
                    dst_crs=destination_crs,
                    dst_nodata=NODATA,
                    resampling=Resampling.nearest,
                )
                available = (destination == NODATA) & (tile != NODATA)
                destination[available] = tile[available]
        else:
            source_bounds = transform_bounds("EPSG:4326", sources[0].crs, *bbox, densify_pts=21)
            mosaic, source_transform = merge(
                sources,
                bounds=source_bounds,
                nodata=NODATA,
                dtype="float32",
                resampling=Resampling.bilinear,
            )
            reproject(
                mosaic[0],
                destination,
                src_transform=source_transform,
                src_crs=sources[0].crs,
                src_nodata=NODATA,
                dst_transform=destination_transform,
                dst_crs=destination_crs,
                dst_nodata=NODATA,
                resampling=Resampling.bilinear,
            )
    finally:
        for source in sources:
            source.close()
    if not np.any(destination != NODATA):
        raise ValueError("source rasters do not intersect the calculation domain")
    return destination, destination_transform, destination_crs


def sample_ray(
    grid: np.ndarray,
    transform: rasterio.Affine,
    azimuth_deg: float,
    distances_m: np.ndarray,
    *,
    categorical: bool = False,
) -> np.ndarray:
    angle = math.radians(azimuth_deg)
    x = np.sin(angle) * distances_m
    y = np.cos(angle) * distances_m
    column = (x - transform.c) / transform.a - 0.5
    row = (y - transform.f) / transform.e - 0.5
    if categorical:
        columns = np.rint(column).astype(int)
        rows = np.rint(row).astype(int)
        inside = (rows >= 0) & (columns >= 0) & (rows < grid.shape[0]) & (columns < grid.shape[1])
        result = np.full(distances_m.shape, NODATA, dtype="float32")
        result[inside] = grid[rows[inside], columns[inside]]
        return result
    c0 = np.floor(column).astype(int)
    r0 = np.floor(row).astype(int)
    inside = (r0 >= 0) & (c0 >= 0) & (r0 + 1 < grid.shape[0]) & (c0 + 1 < grid.shape[1])
    result = np.full(distances_m.shape, NODATA, dtype="float32")
    wr = row[inside] - r0[inside]
    wc = column[inside] - c0[inside]
    sample_rows, sample_columns = r0[inside], c0[inside]
    v00 = grid[sample_rows, sample_columns]
    v10 = grid[sample_rows + 1, sample_columns]
    v01 = grid[sample_rows, sample_columns + 1]
    v11 = grid[sample_rows + 1, sample_columns + 1]
    complete = (v00 != NODATA) & (v10 != NODATA) & (v01 != NODATA) & (v11 != NODATA)
    values = v00 * (1 - wr) * (1 - wc) + v10 * wr * (1 - wc) + v01 * (1 - wr) * wc + v11 * wr * wc
    destination_indices = np.flatnonzero(inside)[complete]
    result[destination_indices] = values[complete]
    return result
