from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from hamrelay_field_strength.terrain import NODATA, load_projected_grid


def write_categorical_tile(
    path: Path,
    *,
    west: float,
    north: float,
    pixel_size: float,
    value: float,
    width: int,
    height: int,
) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(west, north, pixel_size, pixel_size),
        nodata=0,
    ) as target:
        target.write(np.full((height, width), value, dtype="float32"), 1)


def test_categorical_tiles_do_not_create_a_nodata_seam(tmp_path: Path) -> None:
    west = tmp_path / "west.tif"
    east = tmp_path / "east.tif"
    write_categorical_tile(
        west,
        west=-0.2,
        north=0.2,
        pixel_size=0.001,
        value=10,
        width=200,
        height=400,
    )
    # A deliberately different source grid reproduces the condition that made
    # an intermediate categorical mosaic vulnerable to a manufactured seam.
    write_categorical_tile(
        east,
        west=0.0,
        north=0.2,
        pixel_size=0.0008,
        value=50,
        width=250,
        height=500,
    )

    grid, _, _ = load_projected_grid(
        [west, east],
        latitude_deg=0,
        longitude_deg=0,
        radius_km=5,
        resolution_m=100,
        categorical=True,
    )

    assert not np.any(grid == NODATA)
    assert set(np.unique(grid)) == {10.0, 50.0}


def test_first_categorical_source_has_overlap_precedence(tmp_path: Path) -> None:
    first = tmp_path / "first.tif"
    second = tmp_path / "second.tif"
    write_categorical_tile(
        first,
        west=-0.2,
        north=0.2,
        pixel_size=0.001,
        value=10,
        width=400,
        height=400,
    )
    write_categorical_tile(
        second,
        west=-0.2,
        north=0.2,
        pixel_size=0.001,
        value=50,
        width=400,
        height=400,
    )

    grid, _, _ = load_projected_grid(
        [first, second],
        latitude_deg=0,
        longitude_deg=0,
        radius_km=5,
        resolution_m=100,
        categorical=True,
    )

    assert np.all(grid == 10)
