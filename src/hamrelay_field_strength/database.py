from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

DATABASE_PATH = Path(
    os.environ.get("FIELD_STRENGTH_DATABASE", "database/stations.sqlite3")
).resolve()

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY,
    name TEXT,
    latitude_deg REAL NOT NULL CHECK(latitude_deg BETWEEN -80 AND 80),
    longitude_deg REAL NOT NULL CHECK(longitude_deg BETWEEN -180 AND 180),
    coordinates_locked INTEGER NOT NULL DEFAULT 0 CHECK(coordinates_locked IN (0,1)),
    coordinate_source TEXT,
    coordinate_precision_m REAL,
    country_code TEXT,
    locality TEXT,
    site_elevation_m REAL,
    antenna_height_agl_m REAL NOT NULL DEFAULT 10 CHECK(antenna_height_agl_m >= 1),
    tx_frequency_mhz REAL NOT NULL CHECK(tx_frequency_mhz BETWEEN 30 AND 6000),
    rx_frequency_mhz REAL,
    mode TEXT,
    band TEXT,
    polarization TEXT NOT NULL DEFAULT 'vertical',
    erp_w REAL NOT NULL DEFAULT 12 CHECK(erp_w > 0),
    antenna_gain_dbi REAL,
    antenna_azimuth_deg REAL,
    antenna_beamwidth_deg REAL,
    antenna_downtilt_deg REAL,
    status TEXT NOT NULL DEFAULT 'active',
    source TEXT,
    source_record_id TEXT,
    source_updated_at TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    extra_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS stations_coordinates_idx ON stations(latitude_deg, longitude_deg);
CREATE INDEX IF NOT EXISTS stations_filters_idx ON stations(mode, band, country_code, status);
CREATE TABLE IF NOT EXISTS coverage_artifacts (
    station_id TEXT PRIMARY KEY REFERENCES stations(station_id) ON DELETE CASCADE,
    manifest_path TEXT NOT NULL,
    model TEXT NOT NULL,
    radius_km REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class StationRecord(BaseModel):
    station_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    name: str | None = None
    latitude_deg: float = Field(ge=-80, le=80)
    longitude_deg: float = Field(ge=-180, le=180)
    coordinates_locked: bool = False
    coordinate_source: str | None = None
    coordinate_precision_m: float | None = Field(default=None, gt=0)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    locality: str | None = None
    site_elevation_m: float | None = None
    antenna_height_agl_m: float = Field(default=10, ge=1, le=3000)
    tx_frequency_mhz: float = Field(ge=30, le=6000)
    rx_frequency_mhz: float | None = Field(default=None, ge=30, le=6000)
    mode: str | None = None
    band: str | None = None
    polarization: str = Field(default="vertical", pattern="^(horizontal|vertical)$")
    erp_w: float = Field(default=12, gt=0)
    antenna_gain_dbi: float | None = None
    antenna_azimuth_deg: float | None = Field(default=None, ge=0, lt=360)
    antenna_beamwidth_deg: float | None = Field(default=None, gt=0, le=360)
    antenna_downtilt_deg: float | None = Field(default=None, ge=-90, le=90)
    status: str = "active"
    source: str | None = None
    source_record_id: str | None = None
    source_updated_at: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


def initialize() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(SCHEMA)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _record(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["coordinates_locked"] = bool(result["coordinates_locked"])
    result["extra"] = json.loads(result.pop("extra_json"))
    return result


def get_station(station_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM stations WHERE station_id=?", (station_id,)
        ).fetchone()
    return _record(row) if row else None


def list_stations(
    *,
    west: float | None = None,
    south: float | None = None,
    east: float | None = None,
    north: float | None = None,
    mode: str | None = None,
    band: str | None = None,
    country_code: str | None = None,
    status: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses, values = [], []
    for column, value in (
        ("mode", mode),
        ("band", band),
        ("country_code", country_code),
        ("status", status),
    ):
        if value is not None:
            clauses.append(f"{column}=?")
            values.append(value)
    if None not in (west, south, east, north):
        clauses.extend(["longitude_deg BETWEEN ? AND ?", "latitude_deg BETWEEN ? AND ?"])
        values.extend([west, east, south, north])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM stations {where} ORDER BY station_id LIMIT ? OFFSET ?",
            (*values, limit, offset),
        ).fetchall()
    return [_record(row) for row in rows]


def upsert_station(record: StationRecord) -> dict[str, Any]:
    data = record.model_dump(exclude={"extra"})
    columns = list(data) + ["extra_json"]
    values = [data[column] for column in data] + [json.dumps(record.extra, sort_keys=True)]
    placeholders = ",".join("?" for _ in columns)
    updates = []
    protected = {"latitude_deg", "longitude_deg", "coordinate_source", "coordinate_precision_m"}
    for column in columns[1:]:
        if column == "coordinates_locked":
            updates.append(
                "coordinates_locked=CASE WHEN stations.coordinates_locked=1 "
                "THEN 1 ELSE excluded.coordinates_locked END"
            )
            continue
        if column in protected:
            updates.append(
                f"{column}=CASE WHEN stations.coordinates_locked=1 "
                f"THEN stations.{column} ELSE excluded.{column} END"
            )
        else:
            updates.append(f"{column}=excluded.{column}")
    updates.append("updated_at=CURRENT_TIMESTAMP")
    with connect() as connection:
        connection.execute(
            f"INSERT INTO stations ({','.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(station_id) DO UPDATE SET {','.join(updates)}",
            values,
        )
    result = get_station(record.station_id)
    assert result is not None
    return result


def ensure_station(
    station_id: str,
    latitude_deg: float,
    longitude_deg: float,
    frequency_mhz: float,
    antenna_height_agl_m: float,
    polarization: str,
    erp_w: float,
) -> None:
    """Insert a calculation-only station without overwriting richer registry data."""

    with connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO stations(
                station_id,latitude_deg,longitude_deg,tx_frequency_mhz,
                antenna_height_agl_m,polarization,erp_w,source
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                station_id,
                latitude_deg,
                longitude_deg,
                frequency_mhz,
                antenna_height_agl_m,
                polarization,
                erp_w,
                "calculation API",
            ),
        )


def register_coverage(station_id: str, manifest_path: Path, radius_km: float) -> None:
    with connect() as connection:
        connection.execute(
            """INSERT INTO coverage_artifacts(station_id,manifest_path,model,radius_km)
               VALUES(?,?,?,?) ON CONFLICT(station_id) DO UPDATE SET
               manifest_path=excluded.manifest_path, model=excluded.model,
               radius_km=excluded.radius_km, updated_at=CURRENT_TIMESTAMP""",
            (station_id, str(manifest_path), "ITU-R P.1812-8", radius_km),
        )
