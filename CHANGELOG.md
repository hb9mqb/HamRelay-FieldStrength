# Changelog

All notable changes follow Keep a Changelog; versions follow Semantic
Versioning.

## [Unreleased]

## [0.2.0] - 2026-07-19

### Added

- Optional ESA WorldCover class rasters or direct clutter-height rasters as
  explicit P.1812 clutter inputs.
- P.1812 sea/coastal/inland zone rasters with terminal-to-coast distance
  calculation for every modeled path.
- Clutter and radio-climate provenance in calculation manifests and API dataset
  selection metadata.
- Boundary-band assessment with an explicit guard threshold, recommended domain
  expansion, and 100 km operational-cap provenance.
- Explicit checksumable Py1812 digital-map archive input, reloaded in spawned
  macOS and Windows workers instead of relying on inherited module state.

### Changed

- Bumped the calculation algorithm contract to `field-strength-v2`; clutter,
  climatic zones, terminal coast distances, and ITU map provenance now affect
  the reproducible result contract.

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
  a single owned individual-or-composite overlay layer, calculation animation,
  display controls, S-meter pointer popup, and GeoTIFF downloads.
- Both Cesium geographic and standard Web Mercator overlay tile endpoints.
- Cesium overlay controller, opacity and 0–50 dBµV/m threshold sliders, legend,
  and expected S-meter cursor sampling.
- English scientific paper, API/model/data/validation documentation and MIT
  licensing.
- Experimental, currently untested Windows spawn/shared-memory path and CI job.
- Architecture, deployment, host-integration, replacement-readiness,
  troubleshooting, practical-application, demo, roadmap, release, and support
  documentation.
- Structured GitHub issue forms, pull-request template, dependency updates,
  release-note categories, multi-platform CI, and multi-architecture container
  publication with SBOM and provenance.
