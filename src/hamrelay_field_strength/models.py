from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Station(BaseModel):
    """Physical transmitter inputs. ERP defaults only when the source omits it."""

    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    latitude_deg: float = Field(ge=-80, le=80)
    longitude_deg: float = Field(ge=-180, le=180)
    frequency_mhz: float = Field(ge=30, le=6000)
    erp_w: float = Field(default=12.0, gt=0)
    antenna_height_agl_m: float = Field(default=10.0, ge=1, le=3000)
    polarization: Literal["horizontal", "vertical"] = "vertical"


class CalculationRequest(BaseModel):
    station: Station
    dem_paths: list[Path] = Field(min_length=1)
    radio_climate_path: Path | None = None
    output_directory: Path
    radius_km: float = Field(default=100.0, gt=0.25, le=100.0)
    profile_step_m: float = Field(default=50.0, ge=10, le=250)
    radial_step_m: float = Field(default=200.0, ge=50, le=1000)
    output_resolution_m: float = Field(default=60.0, ge=10, le=1000)
    minimum_rays: int = Field(default=360, ge=360, le=20000)
    outer_arc_spacing_m: float = Field(default=500.0, ge=50, le=5000)
    receiver_height_agl_m: float = Field(default=1.5, ge=1, le=3000)
    time_percent: float = Field(default=50.0, ge=1, le=50)
    location_percent: float = Field(default=50.0, ge=1, le=99)
    workers: int | Literal["auto"] = "auto"

    @field_validator("dem_paths")
    @classmethod
    def dem_files_must_exist(cls, value: list[Path]) -> list[Path]:
        missing = [str(path) for path in value if not path.is_file()]
        if missing:
            raise ValueError(f"DEM files do not exist: {', '.join(missing)}")
        return value
