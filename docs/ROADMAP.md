# Roadmap

The roadmap prioritizes scientific integrity and replaceable interfaces over a
larger feature count. An item is complete only when code, tests, documentation,
and provenance agree.

## 0.1 — Public foundation

- [x] ITU-R P.1812-8 terrain-profile calculation in dBµV/m
- [x] P.525 near-field handling below 250 m
- [x] Float32 GeoTIFF and numeric/color tile delivery
- [x] Web Mercator and Cesium geographic tiling
- [x] composite overlays, absolute legend, threshold, and opacity
- [x] cursor sampling and frequency-aware expected S indication
- [x] standalone SQLite registry with coordinate locks
- [x] automatic Copernicus GLO-30 acquisition with GLO-90 fallback
- [x] Leaflet demo, Docker quick start, OpenAPI, and scientific paper
- [x] Apple-silicon multiprocessing and optional MLX/Metal rasterization
- [x] Linux CI and prepared but explicitly untested Windows path

## Optional production-host integrations

- [ ] publish a standalone JSON Schema for the physical/artifact manifest
- [ ] add optional radio-climate dataset acquisition profiles
- [x] add optional WorldCover-class or direct-height clutter rasters under a new model version
- [ ] provide recipes for content-addressed object-storage publication
- [ ] provide example adapters for durable job runners without coupling the core
  to a specific queue
- [ ] provide an optional generic SQL adapter example without making an external
  database mandatory
- [ ] publish a reusable cross-implementation fixture corpus
- [ ] publish measured Apple M5 CPU/Metal equivalence and performance results

These are ecosystem integrations and research extensions, not blockers for the
bounded 0.1 component. Host-specific atomic publication, lifecycle, central
database, and retention remain outside this repository by design. The detailed
embedding criteria are in
[Replacement readiness](REPLACEMENT-READINESS.md).

## Scientific validation

- [ ] expand official/reference P.1812 profile conformance fixtures
- [ ] publish calibrated mobile and fixed measurement schemas
- [ ] add residual reports by terrain, distance, band, and field interval
- [ ] quantify sensitivity to DEM, clutter, antenna height, ERP, and sampling
- [ ] add uncertainty layers without replacing the primary absolute field
- [ ] invite independent replication and dataset review

## Additional runtimes and accelerators

- [ ] test and support Windows on x86-64 and ARM64
- [ ] publish Linux ARM64 and x86-64 benchmarks
- [ ] evaluate CUDA, ROCm, SYCL, Vulkan, and WebGPU backends
- [ ] require each backend to match the NumPy reference within documented tolerances
- [ ] add architecture-specific container build and smoke-test evidence

## Web and GIS ecosystem

- [ ] framework adapters for React, Vue, and Svelte
- [ ] MapLibre and OpenLayers reference integrations
- [ ] accessible keyboard/touch inspection and non-color-only legend cues
- [ ] signed release artifacts and software bill of materials
- [ ] object-storage/CDN publication example
- [ ] optional local numeric-tile sampling to reduce cursor latency

## How to contribute

Open a focused issue before implementing a large item. Explain the use case,
physical assumptions, API/schema effect, validation plan, platform, licensing,
and success criteria. High-quality scientific, validation, performance, web,
accessibility, GIS, and documentation contributions are all welcome. See
[CONTRIBUTING.md](../CONTRIBUTING.md).
