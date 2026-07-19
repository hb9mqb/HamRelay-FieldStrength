import numpy as np
import pytest

from hamrelay_field_strength.palette import decode, quantize, rgba_lut


def test_numeric_tile_round_trip() -> None:
    field = np.array([[-9999.0, -20.0, 0.0, 5.0, 100.0]], dtype="float32")
    values = quantize(field)
    assert values[0, 0] == 0
    assert decode(int(values[0, 1])) == pytest.approx(-20.0)
    assert decode(int(values[0, 2])) == pytest.approx(0.0)
    assert decode(int(values[0, 3])) == pytest.approx(5.0)
    assert decode(0) is None


def test_display_threshold_changes_alpha_only() -> None:
    low, high = rgba_lut(5), rgba_lut(20)
    index_10 = int((10 - (-20)) / 0.5) + 1
    index_30 = int((30 - (-20)) / 0.5) + 1
    assert low[index_10, 3] > 0
    assert high[index_10, 3] == 0
    assert np.array_equal(low[index_30, :3], high[index_30, :3])
