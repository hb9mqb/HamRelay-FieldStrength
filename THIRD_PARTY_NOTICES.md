# Third-party software and data

The MIT License in this repository covers the project's original code and
documentation only. Dependencies, standards, datasets, map tiles, and optional
runtime products remain under their respective terms.

## Runtime software

The authoritative dependency list and version ranges are in
[`pyproject.toml`](pyproject.toml) and [`web/package-lock.json`](web/package-lock.json).
Important components include:

- **Py1812**, the pinned implementation of Recommendation ITU-R P.1812;
- **NumPy**, **Rasterio/GDAL**, and **pyproj/PROJ** for numerical and geospatial
  processing;
- **FastAPI**, **Uvicorn**, and **Pydantic** for the HTTP service;
- **Pillow** for PNG products;
- optional **MLX** for Apple-silicon Metal rasterization;
- **CesiumJS** as a peer dependency of the reusable globe package; and
- **Leaflet** in the reference demo.

Consult each upstream distribution for its exact license and required notices.
Automated dependency metadata is not a substitute for a release-time license
review.

## Standards and integral products

The software implements or references ITU-R Recommendations P.1812 and P.525.
The `DN50.TXT` and `N050.TXT` digital products required by Py1812 are obtained
at runtime under ITU/upstream terms and are not redistributed in this
repository or container image.

## Terrain and base maps

The automatic terrain mode can obtain Copernicus DEM products from AWS Open
Data. Copernicus product terms, attribution requirements, vertical datum, and
accuracy statements continue to apply. Operator-supplied DEMs and visual base
rasters retain their own licenses.

The demo loads Leaflet from unpkg and public OpenStreetMap tiles. OpenStreetMap
copyright, attribution, tile-usage, caching, and privacy policies apply. A
production operator should select and configure an approved provider for its
traffic level; this project does not grant map-tile usage rights.

See [Data sources and provenance](docs/DATA-SOURCES.md) before publishing or
redistributing outputs. Report a missing or inaccurate notice as a bug.
