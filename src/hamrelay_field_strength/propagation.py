from __future__ import annotations

import json
import math
import multiprocessing
import os
import platform
import subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import shared_memory
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Geod
from rasterio.transform import from_origin
from rasterio.warp import Resampling, calculate_default_transform, reproject

from .models import CalculationRequest
from .terrain import NODATA, load_projected_grid, sample_ray

MODEL_ID = "itu-r-p1812-8"
IMPLEMENTATION_ID = "Py1812-a5205e6"
ALGORITHM_VERSION = "field-strength-v1"
GEOD = Geod(ellps="WGS84")
_STATE: dict[str, Any] = {}


def p525_free_space_field_dbuv_m(erp_w: float, distance_km: float) -> float:
    if erp_w <= 0 or distance_km <= 0:
        raise ValueError("ERP and distance must be positive")
    return 76.92 + 10 * math.log10(erp_w) - 20 * math.log10(distance_km)


def _apple_performance_cores() -> int | None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return None
    completed = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "hw.perflevel0.physicalcpu"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return int(completed.stdout.strip()) if completed.returncode == 0 else None
    except ValueError:
        return None


def worker_count(requested: int | str, tasks: int) -> int:
    if requested != "auto":
        return min(int(requested), tasks)
    performance = _apple_performance_cores()
    available = (
        performance - (2 if performance and performance >= 10 else 1)
        if performance
        else (os.cpu_count() or 2) - 2
    )
    return min(max(1, available), tasks)


def _init_worker(state: dict[str, Any]) -> None:
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(variable, "1")
    global _STATE
    _STATE = dict(state)
    _STATE["_shared_handles"] = []
    for key in ("terrain", "zones"):
        descriptor = _STATE.pop(f"{key}_shared", None)
        if descriptor is None:
            continue
        handle = shared_memory.SharedMemory(name=descriptor["name"])
        _STATE["_shared_handles"].append(handle)
        _STATE[key] = np.ndarray(
            tuple(descriptor["shape"]), dtype=np.dtype(descriptor["dtype"]), buffer=handle.buf
        )
    from Py1812 import P1812

    _STATE["p1812"] = P1812


def _ray(task: tuple[int, float]) -> tuple[int, np.ndarray]:
    index, azimuth = task
    state = _STATE
    terrain = sample_ray(state["terrain"], state["transform"], azimuth, state["profile_m"])
    if np.any(terrain == NODATA):
        raise RuntimeError(f"terrain has NoData on azimuth {azimuth:.3f}°")
    if state["zones"] is None:
        zones = np.full(terrain.shape, 4, dtype="uint8")
    else:
        zones = sample_ray(
            state["zones"], state["transform"], azimuth, state["profile_m"], categorical=True
        ).astype("uint8")
        if not np.all(np.isin(zones, (1, 3, 4))):
            raise RuntimeError(f"invalid P.1812 radio-climatic zone on azimuth {azimuth:.3f}°")
    radial_km = state["radial_km"]
    output = np.empty(radial_km.shape, dtype="float32")
    endpoint_indices = np.rint(radial_km * 1000 / state["profile_step_m"]).astype(int)
    endpoint_m = radial_km * 1000
    receiver_lon, receiver_lat, _ = GEOD.fwd(
        np.full(radial_km.shape, state["lon"]),
        np.full(radial_km.shape, state["lat"]),
        np.full(radial_km.shape, azimuth),
        endpoint_m,
    )
    p1812 = state["p1812"]
    for n, (distance, endpoint) in enumerate(zip(radial_km, endpoint_indices, strict=True)):
        if distance < 0.25 or endpoint < 4:
            output[n] = p525_free_space_field_dbuv_m(state["erp_w"], max(distance, 0.001))
            continue
        _, field = p1812.bt_loss(
            state["frequency_mhz"] / 1000,
            state["time_percent"],
            state["profile_km"][: endpoint + 1],
            terrain[: endpoint + 1],
            np.zeros(endpoint + 1, dtype="float64"),
            zones[: endpoint + 1],
            state["tx_agl_m"],
            state["rx_agl_m"],
            state["polarization"],
            state["lat"],
            float(receiver_lat[n]),
            state["lon"],
            float(receiver_lon[n]),
            pL=state["location_percent"],
            Ptx=state["erp_w"] / 1000,
        )
        output[n] = field
    return index, output


def polar_to_cartesian(
    polar: np.ndarray, radius_km: float, radial_step_m: float, output_resolution_m: float
) -> tuple[np.ndarray, rasterio.Affine]:
    reach = radius_km * 1000
    size = math.ceil(2 * reach / output_resolution_m)
    axis = -reach + (np.arange(size) + 0.5) * output_resolution_m
    x, y = np.meshgrid(axis, axis[::-1])
    distance = np.hypot(x, y)
    azimuth = (np.degrees(np.arctan2(x, y)) + 360) % 360
    ai = azimuth / (360 / polar.shape[0])
    a0 = np.floor(ai).astype(int) % polar.shape[0]
    a1 = (a0 + 1) % polar.shape[0]
    aw = ai - np.floor(ai)
    ri = distance / radial_step_m
    r0 = np.clip(np.floor(ri).astype(int), 0, polar.shape[1] - 2)
    r1 = r0 + 1
    rw = np.clip(ri - r0, 0, 1)
    low = polar[a0, r0] * (1 - rw) + polar[a0, r1] * rw
    high = polar[a1, r0] * (1 - rw) + polar[a1, r1] * rw
    field = (low * (1 - aw) + high * aw).astype("float32")
    field[distance > reach] = NODATA
    return field, from_origin(-reach, reach, output_resolution_m, output_resolution_m)


def _share(array: np.ndarray) -> tuple[dict[str, object], shared_memory.SharedMemory]:
    contiguous = np.ascontiguousarray(array)
    handle = shared_memory.SharedMemory(create=True, size=contiguous.nbytes)
    np.ndarray(contiguous.shape, dtype=contiguous.dtype, buffer=handle.buf)[:] = contiguous
    return {"name": handle.name, "shape": contiguous.shape, "dtype": contiguous.dtype.str}, handle


@dataclass(frozen=True)
class Result:
    field_geotiff: Path
    manifest: Path


def calculate(request: CalculationRequest) -> Result:
    request.output_directory.mkdir(parents=True, exist_ok=True)
    terrain, transform, projected_crs = load_projected_grid(
        request.dem_paths,
        request.station.latitude_deg,
        request.station.longitude_deg,
        request.radius_km,
        request.profile_step_m,
    )
    zones = None
    if request.radio_climate_path:
        zones, zone_transform, _ = load_projected_grid(
            [request.radio_climate_path],
            request.station.latitude_deg,
            request.station.longitude_deg,
            request.radius_km,
            request.profile_step_m,
            categorical=True,
        )
        if zone_transform != transform:
            raise RuntimeError("radio-climate grid failed co-registration")
    profile_km = np.arange(
        0, request.radius_km + request.profile_step_m / 2000, request.profile_step_m / 1000
    )
    radial_km = np.arange(
        0.001, request.radius_km + request.radial_step_m / 2000, request.radial_step_m / 1000
    )
    ray_count = max(
        request.minimum_rays,
        math.ceil(2 * math.pi * request.radius_km * 1000 / request.outer_arc_spacing_m),
    )
    azimuths = np.linspace(0, 360, ray_count, endpoint=False)
    state = {
        "terrain": terrain,
        "zones": zones,
        "transform": transform,
        "profile_km": profile_km,
        "profile_m": profile_km * 1000,
        "profile_step_m": request.profile_step_m,
        "radial_km": radial_km,
        "lat": request.station.latitude_deg,
        "lon": request.station.longitude_deg,
        "frequency_mhz": request.station.frequency_mhz,
        "erp_w": request.station.erp_w,
        "tx_agl_m": request.station.antenna_height_agl_m,
        "rx_agl_m": request.receiver_height_agl_m,
        "polarization": 1 if request.station.polarization == "horizontal" else 2,
        "time_percent": request.time_percent,
        "location_percent": request.location_percent,
    }
    polar = np.empty((ray_count, radial_km.size), dtype="float32")
    workers = worker_count(request.workers, ray_count)
    context = multiprocessing.get_context("spawn" if platform.system() == "Darwin" else "fork")
    if workers == 1:
        _init_worker(state)
        results = map(_ray, enumerate(azimuths))
        for index, row in results:
            polar[index] = row
    else:
        worker_state = dict(state)
        handles: list[shared_memory.SharedMemory] = []
        # Both macOS and Windows use spawn. Share immutable grids instead of
        # serializing one private raster copy per worker.
        if context.get_start_method() == "spawn":
            for key in ("terrain", "zones"):
                if worker_state[key] is None:
                    continue
                descriptor, handle = _share(worker_state[key])
                handles.append(handle)
                worker_state[key] = None
                worker_state[f"{key}_shared"] = descriptor
        try:
            with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=context,
                initializer=_init_worker,
                initargs=(worker_state,),
            ) as pool:
                for index, row in pool.map(
                    _ray, enumerate(azimuths), chunksize=max(1, ray_count // (workers * 16))
                ):
                    polar[index] = row
        finally:
            for handle in handles:
                handle.close()
                handle.unlink()
    from . import metal

    if metal.available():
        field = metal.interpolate(
            polar, request.radius_km, request.radial_step_m, request.output_resolution_m, NODATA
        )
        reach = request.radius_km * 1000
        field_transform = from_origin(
            -reach, reach, request.output_resolution_m, request.output_resolution_m
        )
        raster_backend = metal.BACKEND_ID
    else:
        field, field_transform = polar_to_cartesian(
            polar, request.radius_km, request.radial_step_m, request.output_resolution_m
        )
        raster_backend = "numpy-polar-v1"
    projected_path = request.output_directory / "field-strength-aeqd.tif"
    with rasterio.open(
        projected_path,
        "w",
        driver="GTiff",
        width=field.shape[1],
        height=field.shape[0],
        count=1,
        dtype="float32",
        crs=projected_crs,
        transform=field_transform,
        nodata=NODATA,
        compress="deflate",
        tiled=True,
    ) as dataset:
        dataset.write(field, 1)
        dataset.update_tags(units="dBµV/m", model=MODEL_ID, implementation=IMPLEMENTATION_ID)
    destination_crs = "EPSG:4326"
    dst_transform, width, height = calculate_default_transform(
        projected_crs,
        destination_crs,
        field.shape[1],
        field.shape[0],
        *rasterio.transform.array_bounds(*field.shape, field_transform),
    )
    geographic_path = request.output_directory / "field-strength.tif"
    with rasterio.open(
        geographic_path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="float32",
        crs=destination_crs,
        transform=dst_transform,
        nodata=NODATA,
        compress="deflate",
        tiled=True,
    ) as destination:
        reproject(
            field,
            rasterio.band(destination, 1),
            src_transform=field_transform,
            src_crs=projected_crs,
            src_nodata=NODATA,
            dst_transform=dst_transform,
            dst_crs=destination_crs,
            dst_nodata=NODATA,
            resampling=Resampling.bilinear,
        )
    valid = field[field != NODATA]
    geographic_bounds = rasterio.transform.array_bounds(height, width, dst_transform)
    manifest = request.output_directory / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "station": request.station.model_dump(mode="json"),
                "model": MODEL_ID,
                "implementation": IMPLEMENTATION_ID,
                "algorithm": ALGORITHM_VERSION,
                "units": "dBµV/m",
                "radius_km": request.radius_km,
                "profile_step_m": request.profile_step_m,
                "radial_step_m": request.radial_step_m,
                "output_resolution_m": request.output_resolution_m,
                "rays": ray_count,
                "workers": workers,
                "raster_backend": raster_backend,
                "field_min_dbuv_m": float(valid.min()),
                "field_max_dbuv_m": float(valid.max()),
                "bounds_wgs84": list(geographic_bounds),
                "assumptions": {
                    "clutter": "zero representative clutter height",
                    "default_erp_w": 12.0,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return Result(geographic_path, manifest)
