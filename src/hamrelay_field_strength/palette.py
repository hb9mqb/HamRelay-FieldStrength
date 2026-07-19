from __future__ import annotations

import numpy as np

PALETTE_ID = "absolute-dbuv-v1"
VALUE_MIN_DB_UV_M = -20.0
VALUE_STEP_DB = 0.5
PALETTE_STOPS = (
    (0.0, (120, 55, 210)),
    (20.0, (45, 90, 230)),
    (40.0, (0, 205, 225)),
    (60.0, (35, 195, 95)),
    (80.0, (250, 215, 45)),
    (90.0, (255, 135, 30)),
    (100.0, (230, 45, 35)),
)


def rgb(field: float) -> tuple[int, int, int]:
    for (low, left), (high, right) in zip(PALETTE_STOPS, PALETTE_STOPS[1:], strict=False):
        if low <= field <= high:
            weight = (field - low) / (high - low)
            return tuple(round(a + (b - a) * weight) for a, b in zip(left, right, strict=True))
    return PALETTE_STOPS[0][1] if field < 0 else PALETTE_STOPS[-1][1]


def quantize(field: np.ndarray, nodata: float = -9999.0) -> np.ndarray:
    result = np.zeros(field.shape, dtype="uint8")
    valid = np.isfinite(field) & (field != nodata)
    scaled = np.rint((field[valid] - VALUE_MIN_DB_UV_M) / VALUE_STEP_DB).astype("int64") + 1
    result[valid] = np.clip(scaled, 1, 255).astype("uint8")
    return result


def decode(value: int) -> float | None:
    return None if value == 0 else VALUE_MIN_DB_UV_M + (value - 1) * VALUE_STEP_DB


def rgba_lut(minimum_dbuv_m: float = 5.0) -> np.ndarray:
    lut = np.zeros((256, 4), dtype="uint8")
    for index in range(1, 256):
        field = decode(index)
        assert field is not None
        if field < minimum_dbuv_m:
            continue
        lut[index, :3] = rgb(field)
        lut[index, 3] = min(220, 135 + int(max(field, 0) * 0.7))
    return lut
