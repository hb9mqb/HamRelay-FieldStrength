from __future__ import annotations

import math
import os
import urllib.error
import urllib.request
from pathlib import Path

from .terrain import geographic_bbox


def _coordinate(value: int, positive: str, negative: str, width: int) -> str:
    return f"{positive if value >= 0 else negative}{abs(value):0{width}d}_00"


def _copernicus_url(latitude: int, longitude: int, resolution: int) -> tuple[str, str]:
    latitude_name = _coordinate(latitude, "N", "S", 2)
    longitude_name = _coordinate(longitude, "E", "W", 3)
    code = "10" if resolution == 30 else "30"
    bucket = "copernicus-dem-30m" if resolution == 30 else "copernicus-dem-90m"
    name = f"Copernicus_DSM_COG_{code}_{latitude_name}_{longitude_name}_DEM"
    return f"https://{bucket}.s3.amazonaws.com/{name}/{name}.tif", f"{name}.tif"


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tif.partial")
    request = urllib.request.Request(url, headers={"User-Agent": "HamRelay-FieldStrength/0.1"})
    try:
        with (
            urllib.request.urlopen(request, timeout=180) as response,
            temporary.open("wb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def acquire_copernicus_dem(
    latitude_deg: float,
    longitude_deg: float,
    radius_km: float,
    cache_directory: Path,
) -> tuple[list[Path], dict[str, object]]:
    """Cache every public GLO-30 tile, falling back to GLO-90 per missing tile."""

    west, south, east, north = geographic_bbox(latitude_deg, longitude_deg, radius_km)
    paths: list[Path] = []
    resolutions: list[int] = []
    for latitude in range(math.floor(south), math.floor(north - 1e-12) + 1):
        for longitude in range(math.floor(west), math.floor(east - 1e-12) + 1):
            selected: Path | None = None
            for resolution in (30, 90):
                url, filename = _copernicus_url(latitude, longitude, resolution)
                target = cache_directory / f"glo-{resolution}" / filename
                if not target.is_file():
                    try:
                        _download(url, target)
                    except urllib.error.HTTPError as error:
                        if error.code == 404 and resolution == 30:
                            continue
                        raise
                selected = target
                resolutions.append(resolution)
                break
            if selected is None:
                raise RuntimeError(f"no Copernicus DEM tile for {latitude}, {longitude}")
            paths.append(selected)
    return paths, {
        "provider": "Copernicus DEM on AWS Open Data",
        "dataset": "GLO-30 Public with per-tile GLO-90 fallback",
        "registry": "https://registry.opendata.aws/copernicus-dem/",
        "resolutions_m": sorted(set(resolutions)),
        "cache_directory": str(cache_directory),
    }
