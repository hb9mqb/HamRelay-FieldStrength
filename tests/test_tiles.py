import pytest

from hamrelay_field_strength.tiles import geographic_tile_bounds, web_mercator_tile_bounds


def test_cesium_geographic_level_zero() -> None:
    assert geographic_tile_bounds(0, 0, 0) == (-180, -90, 0, 90)
    assert geographic_tile_bounds(0, 1, 0) == (0, -90, 180, 90)


def test_invalid_tile_is_rejected() -> None:
    with pytest.raises(ValueError):
        geographic_tile_bounds(1, 4, 0)


def test_web_mercator_level_zero() -> None:
    west, south, east, north = web_mercator_tile_bounds(0, 0, 0)
    assert west == pytest.approx(-20037508.342789244)
    assert south == pytest.approx(-20037508.342789244)
    assert east == pytest.approx(20037508.342789244)
    assert north == pytest.approx(20037508.342789244)
