from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from .palette import quantize, rgba_lut


def render_visual_geotiff(
    field_path: Path,
    output_path: Path,
    *,
    minimum_dbuv_m: float = 5.0,
    background_path: Path | None = None,
    background_attribution: str = "",
) -> Path:
    """Render transparent or background-composited RGBA without changing field data."""

    with rasterio.open(field_path) as field_source:
        field = field_source.read(1)
        profile = field_source.profile.copy()
        overlay = rgba_lut(minimum_dbuv_m)[
            quantize(field, field_source.nodata if field_source.nodata is not None else -9999.0)
        ]
        if background_path is None:
            output = overlay
        else:
            background = np.zeros((3, field_source.height, field_source.width), dtype="uint8")
            with rasterio.open(background_path) as source:
                if source.count not in {1, 3, 4}:
                    raise ValueError("background GeoTIFF must have 1, 3, or 4 bands")
                for output_band in range(3):
                    source_band = 1 if source.count == 1 else output_band + 1
                    reproject(
                        rasterio.band(source, source_band),
                        background[output_band],
                        src_transform=source.transform,
                        src_crs=source.crs,
                        dst_transform=field_source.transform,
                        dst_crs=field_source.crs,
                        resampling=Resampling.bilinear,
                    )
            alpha = overlay[:, :, 3].astype("float32") / 255.0
            rgb = np.moveaxis(background, 0, 2).astype("float32")
            composite = overlay[:, :, :3] * alpha[:, :, None] + rgb * (1 - alpha[:, :, None])
            output = np.dstack(
                (composite.astype("uint8"), np.full(field.shape, 255, dtype="uint8"))
            )

    profile.update(driver="GTiff", count=4, dtype="uint8", nodata=None, photometric="RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as destination:
        destination.write(np.moveaxis(output, 2, 0))
        destination.update_tags(
            product="rendered field-strength visualization",
            field_units="dBµV/m",
            minimum_field_strength_dbuv_m=str(minimum_dbuv_m),
            background_attribution=background_attribution,
            warning="Visual product; use field-strength.tif for numerical analysis",
        )
    return output_path
