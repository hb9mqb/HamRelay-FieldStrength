import pytest

from hamrelay_field_strength.propagation import p525_free_space_field_dbuv_m
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
