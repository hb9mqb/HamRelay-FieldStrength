from __future__ import annotations

import glob
import io
import json
import math
import os
import re
import threading
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import rasterio
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field, model_validator

from .database import (
    StationRecord,
    ensure_station,
    get_station,
    list_stations,
    register_coverage,
    upsert_station,
)
from .database import (
    initialize as initialize_database,
)
from .models import CalculationRequest, Station
from .palette import PALETTE_ID, PALETTE_STOPS, rgba_lut
from .propagation import calculate
from .rendered_geotiff import render_visual_geotiff
from .smeter import FieldSample
from .terrain import geographic_bbox
from .terrain_sources import acquire_copernicus_dem
from .tiles import render_tile, render_web_mercator_tile, write_pyramid

ARTIFACT_ROOT = Path(os.environ.get("FIELD_STRENGTH_ARTIFACT_ROOT", "artifacts")).resolve()
app = FastAPI(
    title="HamRelay Field Strength API",
    version="1.0.0",
    description=(
        "Terrain-aware dBµV/m calculation, station registry, artifact delivery, "
        "web-map overlays, and point sampling."
    ),
    license_info={"name": "MIT", "identifier": "MIT"},
)
_cors_origins = [
    origin.strip()
    for origin in os.environ.get("FIELD_STRENGTH_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )
_JOBS: dict[str, dict[str, object]] = {}
_JOBS_LOCK = threading.Lock()
initialize_database()


class AnalysisRequest(BaseModel):
    """Safe HTTP calculation inputs; server-side dataset IDs replace paths."""

    station: Station | None = None
    station_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    terrain_mode: Literal["dataset", "auto"] = "auto"
    dem_dataset_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    radius_km: float = Field(default=100.0, gt=0.25, le=100.0)
    output_formats: set[Literal["geotiff", "tiles"]] = Field(
        default_factory=lambda: {"geotiff", "tiles"}
    )
    geotiff_background: Literal["transparent", "map", "streetmap"] = "transparent"
    minimum_field_strength_dbuv_m: float = Field(default=5.0, ge=0, le=50)

    @model_validator(mode="after")
    def validate_terrain_selection(self) -> AnalysisRequest:
        if (self.station is None) == (self.station_id is None):
            raise ValueError("provide exactly one of station or station_id")
        if self.terrain_mode == "dataset" and not self.dem_dataset_id:
            raise ValueError("dem_dataset_id is required in dataset terrain mode")
        if self.terrain_mode == "auto" and self.dem_dataset_id:
            raise ValueError("dem_dataset_id must be omitted in auto terrain mode")
        return self


class StationImportRequest(BaseModel):
    records: list[StationRecord] = Field(min_length=1, max_length=10000)


class BatchSampleRequest(BaseModel):
    station_ids: list[str] = Field(min_length=1, max_length=64)
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)


def _calculation_enabled() -> bool:
    return os.environ.get("FIELD_STRENGTH_ENABLE_CALCULATIONS", "").lower() in {"1", "true", "yes"}


def _dem_catalog() -> dict[str, dict[str, object]]:
    catalog_path = os.environ.get("FIELD_STRENGTH_DEM_CATALOG")
    if not catalog_path:
        raise RuntimeError("FIELD_STRENGTH_DEM_CATALOG is not configured")
    data = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("DEM catalog must be a JSON object")
    return data


def _basemap_catalog() -> dict[str, dict[str, object]]:
    catalog_path = os.environ.get("FIELD_STRENGTH_BASEMAP_CATALOG")
    if not catalog_path:
        raise RuntimeError("FIELD_STRENGTH_BASEMAP_CATALOG is not configured")
    data = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("basemap catalog must be a JSON object")
    return data


def _select_dem(
    request: AnalysisRequest, catalog: dict[str, dict[str, object]]
) -> tuple[str, dict[str, object]]:
    if request.terrain_mode == "dataset":
        entry = catalog.get(str(request.dem_dataset_id))
        if not isinstance(entry, dict):
            raise ValueError(f"unknown DEM dataset: {request.dem_dataset_id}")
        return str(request.dem_dataset_id), entry

    station = _analysis_station(request)
    requested = geographic_bbox(station.latitude_deg, station.longitude_deg, request.radius_km)
    candidates: list[tuple[float, float, str, dict[str, object]]] = []
    for dataset_id, entry in catalog.items():
        bounds = entry.get("bounds")
        paths = entry.get("dem_paths")
        if not isinstance(bounds, list) or len(bounds) != 4 or not isinstance(paths, list):
            continue
        if not entry.get("auto_provider") and not _expand_dem_paths(entry):
            continue
        west, south, east, north = (float(value) for value in bounds)
        if (
            west <= requested[0]
            and south <= requested[1]
            and east >= requested[2]
            and north >= requested[3]
        ):
            candidates.append(
                (
                    -float(entry.get("priority", 0)),
                    float(entry.get("resolution_m", float("inf"))),
                    dataset_id,
                    entry,
                )
            )
    if not candidates:
        raise ValueError("no registered DEM covers the complete calculation radius")
    _, _, dataset_id, entry = min(candidates)
    return dataset_id, entry


def _expand_dem_paths(entry: dict[str, object]) -> list[Path]:
    paths: list[Path] = []
    for pattern in entry.get("dem_paths", []):
        paths.extend(Path(path) for path in glob.glob(str(pattern)))
    return sorted(set(paths))


def _analysis_station(request: AnalysisRequest) -> Station:
    if request.station is not None:
        return request.station
    record = get_station(str(request.station_id))
    if record is None:
        raise ValueError(f"unknown station_id: {request.station_id}")
    return Station(
        id=record["station_id"],
        latitude_deg=record["latitude_deg"],
        longitude_deg=record["longitude_deg"],
        frequency_mhz=record["tx_frequency_mhz"],
        erp_w=record["erp_w"],
        antenna_height_agl_m=record["antenna_height_agl_m"],
        polarization=record["polarization"],
    )


def _run_analysis(job_id: str, request: AnalysisRequest) -> None:
    try:
        station = _analysis_station(request)
        ensure_station(
            station.id,
            station.latitude_deg,
            station.longitude_deg,
            station.frequency_mhz,
            station.antenna_height_agl_m,
            station.polarization,
            station.erp_w,
        )
        selected_dataset_id, entry = _select_dem(request, _dem_catalog())
        if not isinstance(entry.get("dem_paths"), list):
            raise ValueError(f"DEM dataset has no dem_paths: {selected_dataset_id}")
        dem_paths = _expand_dem_paths(entry)
        acquisition = None
        if entry.get("auto_provider") == "copernicus-glo30-aws":
            dem_paths, acquisition = acquire_copernicus_dem(
                station.latitude_deg,
                station.longitude_deg,
                request.radius_km,
                Path(str(entry.get("cache_directory", "/cache/dem"))),
            )
        if not dem_paths:
            raise ValueError(f"DEM dataset resolved to no files: {selected_dataset_id}")
        calculation = CalculationRequest(
            station=station,
            dem_paths=dem_paths,
            radio_climate_path=Path(str(entry["radio_climate_path"]))
            if entry.get("radio_climate_path")
            else None,
            output_directory=ARTIFACT_ROOT / station.id,
            radius_km=request.radius_km,
        )
        result = calculate(calculation)
        tile_count = 0
        if "tiles" in request.output_formats:
            tile_count = write_pyramid(result.field_geotiff, calculation.output_directory / "tiles")
        rendered_name = None
        background_metadata = None
        if "geotiff" in request.output_formats:
            rendered_name = f"field-strength-{request.geotiff_background}.tif"
            background_path = None
            attribution = ""
            if request.geotiff_background != "transparent":
                background = _basemap_catalog().get(request.geotiff_background)
                if not isinstance(background, dict):
                    raise ValueError(
                        f"unconfigured GeoTIFF background: {request.geotiff_background}"
                    )
                background_path = Path(str(background.get("raster_path", "")))
                if not background_path.is_file():
                    raise ValueError("configured background raster does not exist")
                attribution = str(background.get("attribution", ""))
                background_metadata = {
                    "style": request.geotiff_background,
                    "attribution": attribution,
                    "license": background.get("license"),
                }
            render_visual_geotiff(
                result.field_geotiff,
                calculation.output_directory / rendered_name,
                minimum_dbuv_m=request.minimum_field_strength_dbuv_m,
                background_path=background_path,
                background_attribution=attribution,
            )
        manifest_data = json.loads(result.manifest.read_text(encoding="utf-8"))
        manifest_data["published_outputs"] = sorted(request.output_formats)
        manifest_data["tile_count"] = tile_count
        manifest_data["terrain_selection"] = {
            "mode": request.terrain_mode,
            "dataset_id": selected_dataset_id,
            "resolution_m": entry.get("resolution_m"),
            "source": entry.get("source"),
            "acquisition": acquisition,
        }
        manifest_data["visual_geotiff"] = (
            {
                "filename": rendered_name,
                "style": request.geotiff_background,
                "minimum_field_strength_dbuv_m": request.minimum_field_strength_dbuv_m,
                "background": background_metadata,
                "numerical_analysis": False,
            }
            if rendered_name
            else None
        )
        result.manifest.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
        register_coverage(station.id, result.manifest, request.radius_km)
        with _JOBS_LOCK:
            _JOBS[job_id] = {
                "job_id": job_id,
                "status": "succeeded",
                "station_id": station.id,
                "radius_km": request.radius_km,
                "dem_dataset_id": selected_dataset_id,
                "manifest": str(result.manifest),
            }
        _manifest.cache_clear()
    except Exception as error:  # the status API must retain worker failures
        with _JOBS_LOCK:
            _JOBS[job_id] = {"job_id": job_id, "status": "failed", "error": str(error)}


def _station_directory(station_id: str) -> Path:
    if re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", station_id) is None:
        raise HTTPException(400, "invalid station_id")
    directory = (ARTIFACT_ROOT / station_id).resolve()
    if ARTIFACT_ROOT not in directory.parents or not directory.is_dir():
        raise HTTPException(404, "coverage artifact not found")
    return directory


@lru_cache(maxsize=512)
def _manifest(station_id: str) -> dict[str, object]:
    return json.loads(
        (_station_directory(station_id) / "manifest.json").read_text(encoding="utf-8")
    )


@app.get("/v1/health", tags=["Operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/demo/")


def _require_admin(api_key: str | None) -> None:
    expected = os.environ.get("FIELD_STRENGTH_ADMIN_API_KEY")
    if not expected:
        raise HTTPException(503, "station write API is disabled")
    if api_key != expected:
        raise HTTPException(401, "invalid API key")


@app.get("/v1/stations", tags=["Stations"])
def stations(
    west: float | None = Query(None, ge=-180, le=180),
    south: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    north: float | None = Query(None, ge=-90, le=90),
    mode: str | None = None,
    band: str | None = None,
    country_code: str | None = None,
    station_status: str | None = Query(None, alias="status"),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    items = list_stations(
        west=west,
        south=south,
        east=east,
        north=north,
        mode=mode,
        band=band,
        country_code=country_code,
        status=station_status,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "count": len(items), "limit": limit, "offset": offset}


@app.get("/v1/stations/{station_id}", tags=["Stations"])
def station_detail(station_id: str) -> dict[str, object]:
    record = get_station(station_id)
    if record is None:
        raise HTTPException(404, "station not found")
    return record


@app.put("/v1/stations/{station_id}", tags=["Stations"])
def write_station(
    station_id: str,
    record: StationRecord,
    api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict[str, object]:
    _require_admin(api_key)
    if record.station_id != station_id:
        raise HTTPException(409, "station_id in path and body differ")
    return upsert_station(record)


@app.post("/v1/stations/import", tags=["Stations"])
def import_stations(
    request: StationImportRequest,
    api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict[str, object]:
    _require_admin(api_key)
    results = [upsert_station(record) for record in request.records]
    return {"imported": len(results), "station_ids": [item["station_id"] for item in results]}


@app.get("/v1/capabilities", tags=["Discovery"])
def capabilities() -> dict[str, object]:
    """Machine-readable feature and limit discovery for web clients."""

    return {
        "api_version": "1.0.0",
        "field_units": "dBµV/m",
        "model": "ITU-R P.1812-8",
        "frequency_mhz": {"minimum": 30, "maximum": 6000},
        "radius_km": {"exclusive_minimum": 0.25, "maximum": 100},
        "terrain_modes": ["dataset", "auto"],
        "output_formats": ["geotiff", "tiles"],
        "visual_geotiff_backgrounds": ["transparent", "map", "streetmap"],
        "maximum_composite_stations": 64,
        "maximum_batch_sample_stations": 64,
        "palette": PALETTE_ID,
        "features": [
            "calculation-jobs",
            "automatic-dem-acquisition",
            "numeric-tiles",
            "rgba-tiles",
            "web-mercator-tiles",
            "server-composites",
            "batch-sampling",
            "expected-s-meter",
            "visual-geotiff",
        ],
    }


@app.get("/v1/legend", tags=["Discovery"])
def legend(frequency_mhz: float = Query(439.5, gt=0)) -> dict[str, object]:
    wavelength = 299.792458 / frequency_mhz
    s9_dbm = -73.0 if frequency_mhz < 30 else -93.0
    s_units = []
    for level in range(1, 10):
        receiver_dbm = s9_dbm - (9 - level) * 6
        field = receiver_dbm - 20 * math.log10(wavelength) + 126.755
        s_units.append(
            {
                "label": f"S{level}",
                "receiver_dbm": receiver_dbm,
                "field_strength_dbuv_m": round(field, 2),
            }
        )
    return {
        "palette_id": PALETTE_ID,
        "units": "dBµV/m",
        "stops": [{"value": value, "rgb": rgb} for value, rgb in PALETTE_STOPS],
        "frequency_mhz": frequency_mhz,
        "expected_s_meter_reference": s_units,
        "receiver_reference": "ideal matched 0 dBi antenna; local losses excluded",
    }


@app.get("/v1/coverages", tags=["Discovery"])
def list_coverages(limit: int = Query(500, ge=1, le=5000)) -> dict[str, object]:
    items: list[dict[str, object]] = []
    if ARTIFACT_ROOT.is_dir():
        for manifest_path in sorted(ARTIFACT_ROOT.glob("*/manifest.json")):
            if len(items) >= limit:
                break
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                station = data.get("station", {})
                items.append(
                    {
                        "station_id": station.get("id"),
                        "latitude_deg": station.get("latitude_deg"),
                        "longitude_deg": station.get("longitude_deg"),
                        "frequency_mhz": station.get("frequency_mhz"),
                        "bounds_wgs84": data.get("bounds_wgs84"),
                        "field_min_dbuv_m": data.get("field_min_dbuv_m"),
                        "field_max_dbuv_m": data.get("field_max_dbuv_m"),
                        "published_outputs": data.get("published_outputs", []),
                    }
                )
            except (OSError, ValueError, AttributeError):
                continue
    return {"items": items, "count": len(items), "limit": limit}


def _sample_station(
    station_id: str, latitude_deg: float, longitude_deg: float
) -> dict[str, object]:
    directory = _station_directory(station_id)
    with rasterio.open(directory / "field-strength.tif") as dataset:
        value = float(next(dataset.sample([(longitude_deg, latitude_deg)]))[0])
        if not np.isfinite(value) or value == dataset.nodata:
            raise HTTPException(404, "coordinate is outside the calculated field")
    data = _manifest(station_id)
    frequency = float(dict(data["station"])["frequency_mhz"])
    result = FieldSample.from_field(value, frequency)
    return {
        "station_id": station_id,
        "field_strength_dbuv_m": round(result.field_strength_dbuv_m, 2),
        "expected_receiver_dbm": round(result.expected_receiver_dbm, 2),
        "expected_s_meter": result.expected_s_meter,
    }


@app.post("/v1/samples", tags=["Coverage"])
def batch_sample(request: BatchSampleRequest) -> dict[str, object]:
    samples: list[dict[str, object]] = []
    for station_id in dict.fromkeys(request.station_ids):
        try:
            samples.append(_sample_station(station_id, request.latitude_deg, request.longitude_deg))
        except HTTPException as error:
            if error.status_code != 404:
                raise
    samples.sort(key=lambda item: float(item["field_strength_dbuv_m"]), reverse=True)
    return {
        "latitude_deg": request.latitude_deg,
        "longitude_deg": request.longitude_deg,
        "strongest": samples[0] if samples else None,
        "samples": samples,
    }


@app.get("/v1/composites/tiles/{z}/{x}/{y}.png", tags=["Coverage"])
def composite_tile(
    z: int,
    x: int,
    y: int,
    station_ids: str = Query(min_length=1),
    minimum_field_strength_dbuv_m: float = Query(5, ge=0, le=50),
    opacity: float = Query(0.7, ge=0, le=1),
) -> Response:
    identifiers = list(
        dict.fromkeys(value.strip() for value in station_ids.split(",") if value.strip())
    )
    if len(identifiers) > 64:
        raise HTTPException(422, "at most 64 stations can be composited")
    strongest = np.zeros((256, 256), dtype="uint8")
    for station_id in identifiers:
        payload = render_tile(
            _station_directory(station_id) / "field-strength.tif", z, x, y, numeric=True
        )
        if payload:
            strongest = np.maximum(strongest, np.asarray(Image.open(io.BytesIO(payload))))
    if not np.any(strongest):
        return Response(status_code=204)
    rgba = rgba_lut(minimum_field_strength_dbuv_m)[strongest].copy()
    rgba[:, :, 3] = np.rint(rgba[:, :, 3].astype("float32") * opacity).astype("uint8")
    output = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(output, "PNG", optimize=True)
    return Response(
        output.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/v1/composites/web-tiles/{z}/{x}/{y}.png", tags=["Coverage"])
def composite_web_tile(
    z: int,
    x: int,
    y: int,
    station_ids: str = Query(min_length=1),
    minimum_field_strength_dbuv_m: float = Query(5, ge=0, le=50),
    opacity: float = Query(0.7, ge=0, le=1),
) -> Response:
    identifiers = list(
        dict.fromkeys(value.strip() for value in station_ids.split(",") if value.strip())
    )
    if len(identifiers) > 64:
        raise HTTPException(422, "at most 64 stations can be composited")
    strongest = np.zeros((256, 256), dtype="uint8")
    for station_id in identifiers:
        payload = render_web_mercator_tile(
            _station_directory(station_id) / "field-strength.tif", z, x, y, numeric=True
        )
        if payload:
            strongest = np.maximum(strongest, np.asarray(Image.open(io.BytesIO(payload))))
    if not np.any(strongest):
        return Response(status_code=204)
    rgba = rgba_lut(minimum_field_strength_dbuv_m)[strongest].copy()
    rgba[:, :, 3] = np.rint(rgba[:, :, 3].astype("float32") * opacity).astype("uint8")
    output = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(output, "PNG", optimize=True)
    return Response(
        output.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=300"}
    )


@app.post("/v1/calculations", status_code=status.HTTP_202_ACCEPTED, tags=["Calculation"])
def submit_calculation(request: AnalysisRequest, background: BackgroundTasks) -> dict[str, object]:
    """Submit a radius-limited analysis using a server-registered DEM dataset."""

    if not _calculation_enabled():
        raise HTTPException(403, "calculation API is disabled")
    try:
        _select_dem(request, _dem_catalog())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    try:
        station = _analysis_station(request)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "queued",
        "station_id": station.id,
        "radius_km": request.radius_km,
        "terrain_mode": request.terrain_mode,
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    background.add_task(_run_analysis, job_id, request)
    return job


@app.get("/v1/calculations/{job_id}", tags=["Calculation"])
def calculation_status(job_id: str) -> dict[str, object]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "calculation job not found")
    return job


@app.get("/v1/coverage/{station_id}/manifest", tags=["Coverage"])
def manifest(station_id: str) -> dict[str, object]:
    return _manifest(station_id)


@app.get("/v1/coverage/{station_id}/field-strength.tif", tags=["Coverage"])
def field_strength_geotiff(station_id: str) -> FileResponse:
    """Download the requested Float32 EPSG:4326 field-strength GeoTIFF."""

    data = _manifest(station_id)
    outputs = data.get("published_outputs", [])
    if "geotiff" not in outputs:
        raise HTTPException(404, "GeoTIFF was not selected for publication")
    path = _station_directory(station_id) / "field-strength.tif"
    return FileResponse(
        path,
        media_type="image/tiff; application=geotiff",
        filename=f"{station_id}-field-strength-dbuv-m.tif",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/v1/coverage/{station_id}/field-strength-visual.tif", tags=["Coverage"])
def visual_field_strength_geotiff(station_id: str) -> FileResponse:
    """Download the optional transparent/map/street-map visual GeoTIFF."""

    visual = _manifest(station_id).get("visual_geotiff")
    if not isinstance(visual, dict) or not visual.get("filename"):
        raise HTTPException(404, "visual GeoTIFF was not requested")
    path = _station_directory(station_id) / str(visual["filename"])
    return FileResponse(
        path,
        media_type="image/tiff; application=geotiff",
        filename=f"{station_id}-field-strength-visual.tif",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/v1/coverage/{station_id}/tiles/{z}/{x}/{y}.png", tags=["Coverage"])
def color_tile(
    station_id: str,
    z: int,
    x: int,
    y: int,
    minimum_field_strength_dbuv_m: float = Query(5, ge=0, le=50),
) -> Response:
    payload = render_tile(
        _station_directory(station_id) / "field-strength.tif",
        z,
        x,
        y,
        minimum_dbuv_m=minimum_field_strength_dbuv_m,
    )
    if payload is None:
        return Response(status_code=204)
    return Response(
        payload, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"}
    )


@app.get("/v1/coverage/{station_id}/web-tiles/{z}/{x}/{y}.png", tags=["Coverage"])
def web_color_tile(
    station_id: str,
    z: int,
    x: int,
    y: int,
    minimum_field_strength_dbuv_m: float = Query(5, ge=0, le=50),
) -> Response:
    payload = render_web_mercator_tile(
        _station_directory(station_id) / "field-strength.tif",
        z,
        x,
        y,
        minimum_dbuv_m=minimum_field_strength_dbuv_m,
    )
    if payload is None:
        return Response(status_code=204)
    return Response(
        payload, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"}
    )


@app.get("/v1/coverage/{station_id}/values/{z}/{x}/{y}.png", tags=["Coverage"])
def value_tile(station_id: str, z: int, x: int, y: int) -> Response:
    payload = render_tile(
        _station_directory(station_id) / "field-strength.tif", z, x, y, numeric=True
    )
    if payload is None:
        return Response(status_code=204)
    return Response(
        payload,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/v1/coverage/{station_id}/sample", tags=["Coverage"])
def sample(
    station_id: str,
    latitude_deg: float = Query(ge=-90, le=90),
    longitude_deg: float = Query(ge=-180, le=180),
) -> dict[str, object]:
    result = _sample_station(station_id, latitude_deg, longitude_deg)
    return {
        **result,
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "receiver_reference": "ideal matched 0 dBi antenna; local losses excluded",
    }


DEMO_ROOT = Path(
    os.environ.get("FIELD_STRENGTH_DEMO_ROOT", Path(__file__).resolve().parents[2] / "demo")
)
if DEMO_ROOT.is_dir():
    app.mount("/demo", StaticFiles(directory=DEMO_ROOT, html=True), name="demo")
