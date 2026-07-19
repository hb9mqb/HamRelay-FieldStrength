from pathlib import Path

import pytest
from pydantic import ValidationError

from hamrelay_field_strength.models import CalculationRequest, Station
from hamrelay_field_strength.service import AnalysisRequest


def station() -> Station:
    return Station(id="TEST-UHF-001", latitude_deg=46.8, longitude_deg=8.2, frequency_mhz=439.5)


def test_erp_defaults_to_twelve_watts() -> None:
    record = station()
    assert record.erp_w == 12.0
    assert record.power_assumed is True


def test_explicit_erp_is_not_marked_assumed() -> None:
    record = Station(
        id="TEST-ACTUAL",
        latitude_deg=46.8,
        longitude_deg=8.2,
        frequency_mhz=439.5,
        erp_w=12,
    )
    assert record.power_assumed is False


@pytest.mark.parametrize("station_id", [".", "..", "-station", "station-"])
def test_station_id_cannot_be_a_path_segment(station_id: str) -> None:
    with pytest.raises(ValidationError):
        Station(
            id=station_id,
            latitude_deg=46.8,
            longitude_deg=8.2,
            frequency_mhz=439.5,
        )


def test_analysis_radius_is_capped() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(
            station=station(),
            terrain_mode="dataset",
            dem_dataset_id="world",
            radius_km=100.1,
        )


def test_analysis_can_request_geotiff() -> None:
    request = AnalysisRequest(
        station=station(),
        terrain_mode="dataset",
        dem_dataset_id="world",
        radius_km=75,
        output_formats={"geotiff"},
    )
    assert request.output_formats == {"geotiff"}


def test_auto_terrain_forbids_dataset_id() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(station=station(), terrain_mode="auto", dem_dataset_id="world")


def test_visual_geotiff_modes() -> None:
    request = AnalysisRequest(
        station=station(),
        terrain_mode="dataset",
        dem_dataset_id="world",
        output_formats={"geotiff"},
        geotiff_background="streetmap",
        minimum_field_strength_dbuv_m=12,
    )
    assert request.geotiff_background == "streetmap"
    assert request.minimum_field_strength_dbuv_m == 12


def test_missing_dem_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        CalculationRequest(
            station=station(), dem_paths=[tmp_path / "missing.tif"], output_directory=tmp_path
        )


def test_workers_are_bounded(tmp_path: Path) -> None:
    dem = tmp_path / "dem.tif"
    dem.touch()
    request = CalculationRequest(
        station=station(), dem_paths=[dem], output_directory=tmp_path, workers=4
    )
    assert request.workers == 4

    with pytest.raises(ValidationError):
        CalculationRequest(station=station(), dem_paths=[dem], output_directory=tmp_path, workers=0)


def test_missing_clutter_raster_is_rejected(tmp_path: Path) -> None:
    dem = tmp_path / "dem.tif"
    dem.touch()
    with pytest.raises(ValidationError):
        CalculationRequest(
            station=station(),
            dem_paths=[dem],
            clutter_paths=[tmp_path / "missing-worldcover.tif"],
            output_directory=tmp_path,
        )


def test_missing_itu_map_archive_is_rejected(tmp_path: Path) -> None:
    dem = tmp_path / "dem.tif"
    dem.touch()
    with pytest.raises(ValidationError):
        CalculationRequest(
            station=station(),
            dem_paths=[dem],
            itu_digital_maps_path=tmp_path / "missing-p1812.npz",
            output_directory=tmp_path,
        )
