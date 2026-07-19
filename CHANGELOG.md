# Changelog

All notable changes follow Keep a Changelog; versions follow Semantic
Versioning.

## [Unreleased]

## [0.1.0] - 2026-07-19

### Added

- ITU-R P.1812-8 radial field-strength engine with P.525 near zone.
- Actual ERP input with explicit 12 W missing-value fallback and 100 km cap.
- M5 performance-core scheduling, spawn-safe shared grids and optional MLX/Metal
  polar rasterization.
- GeoTIFF, numerical geographic tiles and absolute-color overlay tiles.
- Embedded SQLite station registry with protected, manually locked coordinates.
- Read-only artifact API plus opt-in radius-controlled calculation API, automatic
  Copernicus DEM acquisition, batch sampling, composite layers, and capability
  discovery.
- Leaflet street-map demo covering station import, filters, calculation jobs,
  individual and strongest-field composite overlays, display controls, S-meter
  inspection, and GeoTIFF downloads.
- Both Cesium geographic and standard Web Mercator overlay tile endpoints.
- Cesium overlay controller, opacity and 0–50 dBµV/m threshold sliders, legend,
  and expected S-meter cursor sampling.
- English scientific paper, API/model/data/validation documentation and MIT
  licensing.
- Experimental, currently untested Windows spawn/shared-memory path and CI job.
