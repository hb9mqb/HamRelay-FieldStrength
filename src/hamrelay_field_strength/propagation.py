from __future__ import annotations

import hashlib
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
from typing import Any, Literal

import numpy as np
import rasterio
from pyproj import Geod
from rasterio.transform import from_origin
from rasterio.warp import Resampling, calculate_default_transform, reproject

from .models import CalculationRequest
from .terrain import NODATA, load_projected_grid, sample_ray

MODEL_ID = "itu-r-p1812-8"
IMPLEMENTATION_ID = "Py1812-a5205e6"
ALGORITHM_VERSION = "field-strength-v2"
GEOD = Geod(ellps="WGS84")
_STATE: dict[str, Any] = {}


def _file_provenance(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    result: dict[str, object] = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }
    with rasterio.open(path) as dataset:
        tags = dataset.tags()
        result["raster"] = {
            "crs": str(dataset.crs),
            "width": dataset.width,
            "height": dataset.height,
            "dtype": dataset.dtypes[0],
            "nodata": dataset.nodata,
            "pixel_size_crs_units": [abs(dataset.transform.a), abs(dataset.transform.e)],
            "bounds": list(dataset.bounds),
            "vertical_datum": tags.get("VERTICAL_DATUM", "unspecified"),
        }
    return result


def _binary_file_provenance(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"filename": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def p525_free_space_field_dbuv_m(erp_w: float, distance_km: float) -> float:
    if erp_w <= 0 or distance_km <= 0:
        raise ValueError("ERP and distance must be positive")
    return 76.92 + 10 * math.log10(erp_w) - 20 * math.log10(distance_km)


def worldcover_clutter_heights(classes: np.ndarray) -> np.ndarray:
    """Map ESA WorldCover classes to documented representative clutter heights."""

    heights = np.zeros(classes.shape, dtype="float32")
    heights[np.isclose(classes, 10)] = 15.0  # tree cover
    heights[np.isclose(classes, 20)] = 3.0  # shrubland
    heights[np.isclose(classes, 50)] = 15.0  # built-up
    heights[np.isclose(classes, 90)] = 1.0  # herbaceous wetland
    heights[np.isclose(classes, 95)] = 10.0  # mangroves
    heights[classes == NODATA] = NODATA
    return heights


def terminal_coast_distances_km(distances_km: np.ndarray, zones: np.ndarray) -> tuple[float, float]:
    """Return P.1812 terminal-to-coast distances for zone codes 1, 3 and 4."""

    if distances_km.ndim != 1 or zones.shape != distances_km.shape or distances_km.size < 2:
        raise ValueError("radio-climate path must be a one-dimensional sampled profile")
    if not np.all(np.isin(zones, (1, 3, 4))):
        raise ValueError("radio-climate profile contains unsupported P.1812 zones")

    def from_terminal(reverse: bool) -> float:
        path_zones = zones[::-1] if reverse else zones
        path_distances = distances_km[-1] - distances_km[::-1] if reverse else distances_km
        if path_zones[0] == 1:
            return 0.0
        sea = np.flatnonzero(path_zones == 1)
        if sea.size == 0:
            return 500.0
        first = int(sea[0])
        if first == 0:
            return 0.0
        return float((path_distances[first - 1] + path_distances[first]) / 2.0)

    return from_terminal(False), from_terminal(True)


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


def process_start_method() -> Literal["spawn", "fork"]:
    """Use spawn where fork is unavailable or unsafe with platform frameworks."""

    return "spawn" if platform.system() in {"Darwin", "Windows"} else "fork"


def _init_worker(state: dict[str, Any]) -> None:
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(variable, "1")
    global _STATE
    _STATE = dict(state)
    _STATE["_shared_handles"] = []
    for key in ("terrain", "clutter", "zones"):
        descriptor = _STATE.pop(f"{key}_shared", None)
        if descriptor is None:
            continue
        handle = shared_memory.SharedMemory(name=descriptor["name"])
        _STATE["_shared_handles"].append(handle)
        _STATE[key] = np.ndarray(
            tuple(descriptor["shape"]), dtype=np.dtype(descriptor["dtype"]), buffer=handle.buf
        )
    from Py1812 import P1812

    itu_maps_path = _STATE.get("itu_digital_maps_path")
    if itu_maps_path:
        with np.load(str(itu_maps_path)) as archive:
            maps = {name: archive[name].copy() for name in ("DN50", "N050")}
        if any(
            matrix.shape != (121, 241) or not np.all(np.isfinite(matrix))
            for matrix in maps.values()
        ):
            raise RuntimeError("ITU digital maps have invalid shape or values")
        P1812.DigitalMaps.clear()
        P1812.DigitalMaps.update(maps)

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
    if state["clutter"] is None:
        clutter = np.zeros(terrain.shape, dtype="float64")
    else:
        clutter = sample_ray(
            state["clutter"], state["transform"], azimuth, state["profile_m"], categorical=True
        ).astype("float64")
        if np.any(clutter == NODATA) or np.any(clutter < 0):
            raise RuntimeError(f"clutter has invalid samples on azimuth {azimuth:.3f}°")
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
        path_distances = state["profile_km"][: endpoint + 1]
        path_zones = zones[: endpoint + 1]
        dct_km, dcr_km = terminal_coast_distances_km(path_distances, path_zones)
        _, field = p1812.bt_loss(
            state["frequency_mhz"] / 1000,
            state["time_percent"],
            path_distances,
            terrain[: endpoint + 1],
            clutter[: endpoint + 1],
            path_zones,
            state["tx_agl_m"],
            state["rx_agl_m"],
            state["polarization"],
            state["lat"],
            float(receiver_lat[n]),
            state["lon"],
            float(receiver_lon[n]),
            pL=state["location_percent"],
            Ptx=state["erp_w"] / 1000,
            dct=dct_km,
            dcr=dcr_km,
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


@dataclass(frozen=True)
class BoundaryAssessment:
    boundary_band_km: float
    boundary_max_dbuv_m: float
    guard_threshold_dbuv_m: float
    open_at_boundary: bool
    recommended_radius_km: float
    range_cap_applied: bool


def assess_service_boundary(
    projected_field_geotiff: Path,
    *,
    radius_km: float,
    guard_threshold_dbuv_m: float,
    boundary_band_km: float = 5.0,
    expansion_km: float = 20.0,
    maximum_radius_km: float = 100.0,
) -> BoundaryAssessment:
    """Assess whether a modeled field remains open near its radial boundary."""

    if not 0 < boundary_band_km < radius_km:
        raise ValueError("boundary band must be positive and smaller than the radius")
    if expansion_km <= 0 or maximum_radius_km < radius_km:
        raise ValueError("domain expansion and maximum radius are inconsistent")
    with rasterio.open(projected_field_geotiff) as source:
        if source.crs is None or not source.crs.is_projected:
            raise ValueError("boundary assessment requires a projected metric field raster")
        field = source.read(1)
        rows, columns = np.indices(field.shape, dtype="float64")
        xs = source.transform.c + (columns + 0.5) * source.transform.a
        ys = source.transform.f + (rows + 0.5) * source.transform.e
        distance_km = np.hypot(xs, ys) / 1000.0
        valid = np.isfinite(field) & (field != source.nodata)
        boundary = valid & (distance_km >= radius_km - boundary_band_km)
        if not np.any(boundary):
            raise RuntimeError("field raster has no valid samples in its boundary band")
        boundary_max = float(np.max(field[boundary]))
    is_open = boundary_max >= guard_threshold_dbuv_m
    next_radius = min(maximum_radius_km, radius_km + expansion_km) if is_open else radius_km
    return BoundaryAssessment(
        boundary_band_km=boundary_band_km,
        boundary_max_dbuv_m=boundary_max,
        guard_threshold_dbuv_m=guard_threshold_dbuv_m,
        open_at_boundary=is_open,
        recommended_radius_km=next_radius,
        range_cap_applied=is_open and radius_km >= maximum_radius_km,
    )


def calculate(request: CalculationRequest) -> Result:
    request.output_directory.mkdir(parents=True, exist_ok=True)
    dem_provenance = [_file_provenance(path) for path in request.dem_paths]
    radio_climate = (
        {
            "mode": "raster",
            "zone_codes": [1, 3, 4],
            "input": _file_provenance(request.radio_climate_path),
        }
        if request.radio_climate_path
        else {
            "mode": "assumed-inland",
            "zone_code": 4,
            "warning": "Not suitable for defensible coastal predictions.",
        }
    )
    terrain, transform, projected_crs = load_projected_grid(
        request.dem_paths,
        request.station.latitude_deg,
        request.station.longitude_deg,
        request.radius_km,
        request.profile_step_m,
    )
    clutter = None
    clutter_provenance: list[dict[str, object]] = []
    if request.clutter_paths:
        clutter_classes, clutter_transform, clutter_crs = load_projected_grid(
            request.clutter_paths,
            request.station.latitude_deg,
            request.station.longitude_deg,
            request.radius_km,
            request.profile_step_m,
            categorical=True,
        )
        if clutter_transform != transform or clutter_crs != projected_crs:
            raise RuntimeError("clutter and terrain grids are not co-registered")
        clutter = (
            worldcover_clutter_heights(clutter_classes)
            if request.clutter_mode == "worldcover_classes"
            else clutter_classes
        )
        if np.any((clutter != NODATA) & (clutter < 0)):
            raise ValueError("clutter heights must not be negative")
        clutter_provenance = [_file_provenance(path) for path in request.clutter_paths]
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
        "clutter": clutter,
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
        "itu_digital_maps_path": (
            str(request.itu_digital_maps_path) if request.itu_digital_maps_path else None
        ),
    }
    polar = np.empty((ray_count, radial_km.size), dtype="float32")
    workers = worker_count(request.workers, ray_count)
    context = multiprocessing.get_context(process_start_method())
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
            for key in ("terrain", "clutter", "zones"):
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
    boundary = assess_service_boundary(
        projected_path,
        radius_km=request.radius_km,
        guard_threshold_dbuv_m=17.0,
        boundary_band_km=min(5.0, request.radius_km / 2.0),
        maximum_radius_km=100.0,
    )
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
                "published_outputs": ["geotiff"],
                "radius_km": request.radius_km,
                "profile_step_m": request.profile_step_m,
                "radial_step_m": request.radial_step_m,
                "output_resolution_m": request.output_resolution_m,
                "minimum_rays": request.minimum_rays,
                "outer_arc_spacing_m": request.outer_arc_spacing_m,
                "rays": ray_count,
                "workers": workers,
                "raster_backend": raster_backend,
                "boundary_assessment": {
                    "boundary_band_km": boundary.boundary_band_km,
                    "boundary_max_dbuv_m": boundary.boundary_max_dbuv_m,
                    "guard_threshold_dbuv_m": boundary.guard_threshold_dbuv_m,
                    "open_at_boundary": boundary.open_at_boundary,
                    "recommended_radius_km": boundary.recommended_radius_km,
                    "range_cap_applied": boundary.range_cap_applied,
                },
                "field_min_dbuv_m": float(valid.min()),
                "field_max_dbuv_m": float(valid.max()),
                "bounds_wgs84": list(geographic_bounds),
                "receiver": {
                    "height_agl_m": request.receiver_height_agl_m,
                    "time_percent": request.time_percent,
                    "location_percent": request.location_percent,
                },
                "terrain_inputs": dem_provenance,
                "clutter": {
                    "mode": request.clutter_mode if request.clutter_paths else "none",
                    "inputs": clutter_provenance,
                    "representative_height_mapping_m": {
                        "tree_cover": 15,
                        "shrubland": 3,
                        "built_up": 15,
                        "herbaceous_wetland": 1,
                        "mangroves": 10,
                    }
                    if request.clutter_paths and request.clutter_mode == "worldcover_classes"
                    else None,
                },
                "radio_climate": radio_climate,
                "itu_digital_maps": (
                    _binary_file_provenance(request.itu_digital_maps_path)
                    if request.itu_digital_maps_path
                    else {
                        "mode": "package-default",
                        "warning": "Use a checksummed explicit map archive for production runs.",
                    }
                ),
                "raster": {
                    "crs": destination_crs,
                    "nodata": NODATA,
                    "interpolation": "bilinear polar and geographic reprojection",
                },
                "near_field": {
                    "method": "ITU-R P.525 free-space field",
                    "maximum_distance_km": 0.25,
                },
                "assumptions": {
                    "clutter": (
                        "explicit raster"
                        if request.clutter_paths
                        else "zero representative clutter height"
                    ),
                    "default_erp_w": 12.0,
                    "power_assumed": request.station.power_assumed,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return Result(geographic_path, manifest)
