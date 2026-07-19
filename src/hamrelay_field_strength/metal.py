"""Optional native Apple-silicon Metal raster interpolation.

The branch-heavy P.1812 model remains on CPU performance cores. This backend
only accelerates the independent polar-to-Cartesian publication stage and has a
numerically equivalent NumPy fallback.
"""

from __future__ import annotations

import platform

import numpy as np

BACKEND_ID = "mlx-metal-polar-v1"
_SOURCE = r"""
uint elem = thread_position_in_grid.x;
uint size = uint(dims[0]); uint rays = uint(dims[1]); uint radial = uint(dims[2]);
uint row = elem / size; uint col = elem - row * size;
float reach = geometry[0]; float resolution = geometry[1];
float radial_step = geometry[2]; float nodata = geometry[3];
float x = -reach + (float(col) + 0.5f) * resolution;
float y =  reach - (float(row) + 0.5f) * resolution;
float distance = metal::sqrt(x*x + y*y);
if (distance > reach) { out[elem] = nodata; return; }
float azimuth = metal::atan2(x, y) * 57.29577951308232f;
if (azimuth < 0.0f) azimuth += 360.0f;
float ap = azimuth * float(rays) / 360.0f;
uint a0 = uint(metal::floor(ap)) % rays; uint a1 = (a0 + 1u) % rays;
float aw = ap - metal::floor(ap);
float rp = distance / radial_step;
uint r0 = min(uint(metal::floor(rp)), radial - 2u); uint r1 = r0 + 1u;
float rw = metal::clamp(rp - float(r0), 0.0f, 1.0f);
float p00 = polar[a0*radial+r0]; float p01 = polar[a0*radial+r1];
float p10 = polar[a1*radial+r0]; float p11 = polar[a1*radial+r1];
out[elem] = (p00 + (p01-p00)*rw)*(1.0f-aw) + (p10 + (p11-p10)*rw)*aw;
"""


def available() -> bool:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False
    try:
        import mlx.core as mx

        return bool(mx.metal.is_available())
    except (ImportError, RuntimeError):
        return False


def interpolate(
    polar: np.ndarray, radius_km: float, radial_step_m: float, resolution_m: float, nodata: float
) -> np.ndarray:
    if not available():
        raise RuntimeError(
            "Metal backend requires native arm64 macOS, macOS 14+, and the mlx extra"
        )
    import mlx.core as mx

    size = int(np.ceil(2 * radius_km * 1000 / resolution_m))
    kernel = mx.fast.metal_kernel(
        name="hamrelay_polar_to_cartesian_v1",
        input_names=["polar", "geometry", "dims"],
        output_names=["out"],
        source=_SOURCE,
        compile_options={"math_mode": "safe"},
    )
    result = kernel(
        inputs=[
            mx.array(np.ascontiguousarray(polar, dtype="float32")),
            mx.array([radius_km * 1000, resolution_m, radial_step_m, nodata], dtype=mx.float32),
            mx.array([size, polar.shape[0], polar.shape[1]], dtype=mx.int32),
        ],
        grid=(size * size, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[(size, size)],
        output_dtypes=[mx.float32],
    )[0]
    mx.eval(result)
    return np.asarray(result, dtype="float32")
