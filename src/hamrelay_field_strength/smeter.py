from __future__ import annotations

import math
from dataclasses import dataclass

LIGHT_SPEED_M_S = 299_792_458.0


def field_to_receiver_dbm(field_dbuv_m: float, frequency_mhz: float) -> float:
    """Convert E-field to available power for an ideal 0 dBi, matched antenna.

    This is a reference conversion, not a prediction of a particular receiver,
    feed line, antenna pattern, polarization mismatch, or local building loss.
    """

    if frequency_mhz <= 0:
        raise ValueError("frequency_mhz must be positive")
    wavelength_m = LIGHT_SPEED_M_S / (frequency_mhz * 1_000_000.0)
    return field_dbuv_m + 20.0 * math.log10(wavelength_m) - 126.755


def receiver_dbm_to_s_meter(receiver_dbm: float, frequency_mhz: float) -> str:
    """Return the IARU Region 1 nominal S indication (6 dB per S unit)."""

    s9_dbm = -73.0 if frequency_mhz < 30.0 else -93.0
    above_s9 = receiver_dbm - s9_dbm
    if above_s9 >= 0:
        rounded = int(round(above_s9))
        return "S9" if rounded == 0 else f"S9+{rounded} dB"
    s_value = max(1, min(9, int(math.floor(9.0 + above_s9 / 6.0))))
    return f"S{s_value}"


@dataclass(frozen=True)
class FieldSample:
    field_strength_dbuv_m: float
    expected_receiver_dbm: float
    expected_s_meter: str

    @classmethod
    def from_field(cls, field_strength_dbuv_m: float, frequency_mhz: float) -> FieldSample:
        receiver = field_to_receiver_dbm(field_strength_dbuv_m, frequency_mhz)
        return cls(
            field_strength_dbuv_m, receiver, receiver_dbm_to_s_meter(receiver, frequency_mhz)
        )
