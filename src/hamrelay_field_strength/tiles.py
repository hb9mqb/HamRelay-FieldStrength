from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

from .palette import quantize, rgba_lut
from .terrain import NODATA

TILE_SIZE = 256


def geographic_tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Cesium GeographicTilingScheme: level zero is 2×1; Y is north-to-south."""

    if z < 0 or not 0 <= x < 2 ** (z + 1) or not 0 <= y < 2**z:
        raise ValueError("tile coordinate is outside the geographic pyramid")
    span = 180.0 / 2**z
    west = -180 + x * span
    north = 90 - y * span
    return west, north - span, west + span, north


def render_tile(
    geotiff: Path, z: int, x: int, y: int, *, minimum_dbuv_m: float = 5.0, numeric: bool = False
) -> bytes | None:
    bounds = geographic_tile_bounds(z, x, y)
    transform = from_bounds(*bounds, TILE_SIZE, TILE_SIZE)
    field = np.full((TILE_SIZE, TILE_SIZE), NODATA, dtype="float32")
    with rasterio.open(geotiff) as source:
        left, bottom, right, top = source.bounds
        if right < bounds[0] or left > bounds[2] or top < bounds[1] or bottom > bounds[3]:
            return None
        reproject(
            rasterio.band(source, 1),
            field,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=transform,
            dst_crs="EPSG:4326",
            dst_nodata=NODATA,
            resampling=Resampling.bilinear,
        )
    values = quantize(field)
    if not np.any(values):
        return None
    image = (
        Image.fromarray(values, "L")
        if numeric
        else Image.fromarray(rgba_lut(minimum_dbuv_m)[values], "RGBA")
    )
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def web_mercator_tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    if z < 0 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise ValueError("tile coordinate is outside the Web Mercator pyramid")
    origin = 20037508.342789244
    span = 2 * origin / 2**z
    west = -origin + x * span
    north = origin - y * span
    return west, north - span, west + span, north


def render_web_mercator_tile(
    geotiff: Path,
    z: int,
    x: int,
    y: int,
    *,
    minimum_dbuv_m: float = 5.0,
    numeric: bool = False,
) -> bytes | None:
    bounds = web_mercator_tile_bounds(z, x, y)
    transform = from_bounds(*bounds, TILE_SIZE, TILE_SIZE)
    field = np.full((TILE_SIZE, TILE_SIZE), NODATA, dtype="float32")
    with rasterio.open(geotiff) as source:
        reproject(
            rasterio.band(source, 1),
            field,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=transform,
            dst_crs="EPSG:3857",
            dst_nodata=NODATA,
            resampling=Resampling.bilinear,
        )
    values = quantize(field)
    if not np.any(values):
        return None
    image = (
        Image.fromarray(values, "L")
        if numeric
        else Image.fromarray(rgba_lut(minimum_dbuv_m)[values], "RGBA")
    )
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def tile_range(z: int, bounds: tuple[float, float, float, float]) -> tuple[range, range]:
    west, south, east, north = bounds
    span = 180 / 2**z
    max_x, max_y = 2 ** (z + 1) - 1, 2**z - 1
    x0 = max(0, min(max_x, math.floor((west + 180) / span)))
    x1 = max(0, min(max_x, math.floor((east + 180 - 1e-12) / span)))
    y0 = max(0, min(max_y, math.floor((90 - north) / span)))
    y1 = max(0, min(max_y, math.floor((90 - south - 1e-12) / span)))
    return range(x0, x1 + 1), range(y0, y1 + 1)


def write_pyramid(geotiff: Path, output: Path, min_zoom: int = 6, max_zoom: int = 11) -> int:
    count = 0
    with rasterio.open(geotiff) as source:
        bounds = tuple(source.bounds)
    for z in range(min_zoom, max_zoom + 1):
        xs, ys = tile_range(z, bounds)
        for x in xs:
            for y in ys:
                numeric = render_tile(geotiff, z, x, y, numeric=True)
                color = render_tile(geotiff, z, x, y)
                if numeric is None or color is None:
                    continue
                for kind, payload in (("values", numeric), ("color", color)):
                    target = output / kind / str(z) / str(x) / f"{y}.png"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
                count += 1
    return count
