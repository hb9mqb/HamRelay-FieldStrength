import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from hamrelay_field_strength.propagation import (
    assess_service_boundary,
    p525_free_space_field_dbuv_m,
    process_start_method,
    terminal_coast_distances_km,
    worldcover_clutter_heights,
)
from hamrelay_field_strength.smeter import field_to_receiver_dbm, receiver_dbm_to_s_meter


def test_p525_erp_reference() -> None:
    assert p525_free_space_field_dbuv_m(1.0, 1.0) == pytest.approx(76.92)
    assert p525_free_space_field_dbuv_m(1000.0, 10.0) == pytest.approx(86.92)


@pytest.mark.parametrize("erp,distance", [(0, 1), (1, 0), (-1, 1)])
def test_p525_rejects_non_positive_inputs(erp: float, distance: float) -> None:
    with pytest.raises(ValueError):
        p525_free_space_field_dbuv_m(erp, distance)


def test_field_to_receiver_reference_at_one_metre_wavelength() -> None:
    frequency_mhz = 299.792458
    assert field_to_receiver_dbm(33.755, frequency_mhz) == pytest.approx(-93.0, abs=1e-6)


def test_iaru_nominal_s_units() -> None:
    assert receiver_dbm_to_s_meter(-93, 145) == "S9"
    assert receiver_dbm_to_s_meter(-99, 145) == "S8"
    assert receiver_dbm_to_s_meter(-87, 145) == "S9+6 dB"
    assert receiver_dbm_to_s_meter(-73, 14.2) == "S9"


@pytest.mark.parametrize(
    ("system", "expected"),
    [("Darwin", "spawn"), ("Windows", "spawn"), ("Linux", "fork")],
)
def test_platform_process_start_method(monkeypatch, system: str, expected: str) -> None:
    monkeypatch.setattr("hamrelay_field_strength.propagation.platform.system", lambda: system)
    assert process_start_method() == expected


def test_worldcover_classes_map_to_representative_clutter_heights() -> None:
    classes = np.array([[10, 20, 50, 90, 95, 40, -9999]], dtype="float32")
    heights = worldcover_clutter_heights(classes)
    np.testing.assert_array_equal(
        heights,
        np.array([[15, 3, 15, 1, 10, 0, -9999]], dtype="float32"),
    )


def test_terminal_coast_distances_use_path_transitions() -> None:
    distances = np.arange(0.0, 7.0, 1.0)
    zones = np.array([4, 3, 1, 1, 3, 4, 4], dtype="uint8")
    assert terminal_coast_distances_km(distances, zones) == (1.5, 2.5)


def test_inland_path_uses_normative_no_sea_default() -> None:
    distances = np.arange(0.0, 5.0, 1.0)
    zones = np.full(distances.shape, 4, dtype="uint8")
    assert terminal_coast_distances_km(distances, zones) == (500.0, 500.0)


def test_boundary_assessment_requests_expansion_for_open_field(tmp_path) -> None:
    path = tmp_path / "field-aeqd.tif"
    field = np.full((20, 20), 25.0, dtype="float32")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=20,
        height=20,
        count=1,
        dtype="float32",
        crs="EPSG:2056",
        transform=from_origin(-10_000, 10_000, 1_000, 1_000),
        nodata=-9999.0,
    ) as target:
        target.write(field, 1)
    result = assess_service_boundary(
        path,
        radius_km=10,
        boundary_band_km=2,
        guard_threshold_dbuv_m=17,
        expansion_km=20,
        maximum_radius_km=100,
    )
    assert result.open_at_boundary is True
    assert result.recommended_radius_km == 30
    assert result.range_cap_applied is False
