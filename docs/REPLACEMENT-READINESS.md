# Replacement Readiness

This document prevents a reusable propagation package from being mistaken for
an automatically compatible replacement for every existing coverage stack.
“Same picture” is not a sufficient acceptance criterion.

## Scope of replacement

HamRelay Field Strength is intended to replace these bounded capabilities:

1. terrain-aware repeater field-strength calculation;
2. numerical and colored overlay publication;
3. map-layer lifecycle and legend controls; and
4. cursor sampling with an expected S-meter indication.

It is not intended to replace a host application's station importers, central
database, identity model, authentication, membership UI, base maps, or globe.

## Current readiness assessment

Version 0.1.0 is ready to publish as the complete, deliberately bounded
field-strength component described above. It can replace an existing
calculation, overlay, legend, and S-meter implementation once the host connects
its own station and publication contracts. It is intentionally not a replacement
for the surrounding application, and does not need to duplicate those host
responsibilities to be complete within its scope.

The distinction is important: **feature-complete component** does not mean
**zero-change replacement of an entire product**. A thin host adapter is an
expected architectural boundary, not missing propagation functionality.

| Capability | Component status | Embedding status | Host integration action |
|---|---|---|---|
| Absolute field in dBµV/m | Implemented | Semantically compatible | Cross-run numerical fixture comparison |
| ITU-R P.1812-8 + near-field P.525 | Implemented | New method is explicit and versioned | Approve conformance tolerances for the host |
| Actual ERP, 12 W fallback | Implemented | Compatible | Preserve `power_assumed` provenance in host adapter |
| 360° terrain profiles, 100 km cap | Implemented | Compatible | Benchmark representative full-radius stations |
| M5 CPU and optional Metal rasterization | Implemented | Additive | NumPy/Metal equivalence and performance evidence |
| Worldwide automatic DEM | Implemented for Copernicus GLO-30/GLO-90 fallback | Compatible through the public terrain contract | Configure any preferred regional datasets in the host deployment |
| Radio-climate zones | Supported as an optional raster | Explicit policy choice | Supply a production raster when the embedding requires it |
| Surface clutter/building policy | Explicitly zero in the current standalone manifest | Deliberate model boundary | Record the approved no-clutter method version |
| Station registry and coordinate locks | Implemented in SQLite | Host remains authoritative by design | Use host UUIDs and synchronize without changing curated coordinates |
| Float32 GeoTIFF | Implemented | Compatible after schema mapping | Validate CRS, NoData, bounds, unit tags, and provenance |
| Numeric/color tiles | Implemented | URL/manifest adapter needed | Match tiling scheme, zoom range, encoding, and cache keys |
| Versioned immutable host artifacts and SHA-256 contract | Outside component scope | Host-owned by design | Map the component manifest into the host contract |
| Host lifecycle (`pending/computing/ready/stale/failed`) | Reference jobs supplied for standalone use | Host-owned by design | Keep the host's durable queue and transactional status updates |
| Composite overlays | Implemented, up to 64 inputs | Compatible in behavior | Align public limits and cache/version policy |
| Cesium independent layers | Implemented | Host adapter required | Pass the host's UI lifecycle, retry, timeout, and crossfade tests |
| Leaflet reference demo | Implemented | Reference only | Not a production-host acceptance test |
| S-meter mouse popup | Implemented | Semantically compatible | Verify receiver reference and frequency-dependent thresholds |
| Public read-only delivery | Implemented | Deployment policy required | Reverse proxy, TLS, CORS, rate limiting, and CDN tests |
| Automatic obsolete-artifact retirement | Outside component scope | Host-owned by design | Retain host garbage collection and never delete a referenced ready artifact |

## Non-negotiable embedding gates

Legacy calculation and overlay code may be removed only when all gates below
are green and recorded for a tagged release.

### G1 — Input contract

- Immutable station IDs map unambiguously.
- Manual coordinate locks survive every import/update path.
- Frequency, ERP, assumed-power flag, AGL, elevation, and polarization match the
  authoritative record.
- Invalid coordinates and unsupported frequencies fail closed.

### G2 — Physical contract

- Model, implementation, algorithm, ITU products, radio-climate dataset,
  terrain source, clutter policy, receiver height, time/location percentages,
  sampling, and radius are versioned inputs.
- Flat-earth/free-space sanity tests and published P.1812 reference profiles
  pass within documented tolerances.
- Candidate and legacy point samples are compared on an agreed representative
  corpus; every material difference is explained, not merely averaged away.

### G3 — Component artifact contract

- The numerical raster declares `dBµV/m`, valid CRS, NoData, bounds, and a
  complete provenance manifest.
- The host maps the component manifest to any content-derived versions and
  checksums required by its own publication contract.
- Host publication is staged and atomic. A failed calculation cannot replace
  the last ready artifact.
- Numeric tile encoding is fixed and independently tested.

### G4 — Host database and lifecycle

- The central database remains the source of truth.
- Job state is durable across worker and host restarts.
- Publication metadata and ready status commit in one controlled transition.
- Obsolete versions are removed only after a retention period and only when no
  active database pointer references them.

### G5 — Browser behavior

- Single and composite overlays render on all supported base maps and globe
  modes.
- Filter changes show the intended station set without changing the camera.
- Opacity, 0–50 dBµV/m threshold, legend, and S popup work with real artifacts.
- Empty/missing/failed fields produce bounded, actionable UI states.
- Tile retry, timeout, cache-busting, layer cleanup, and memory tests pass.

### G6 — Operations and rollback

- Production-like load, restart, disk-full, partial-download, corrupt-tile, and
  unavailable-terrain tests pass.
- Metrics expose queue depth, duration, failure class, artifact age, and tile
  errors.
- A documented command can restore the previous tagged package/image and
  artifact pointer without recalculation.

## Recommended embedding strategy

Treat the new repository as an independently released dependency, not copied
source. Pin either:

- a Python package tag in the existing durable worker; or
- a versioned OCI image behind an internal API.

Add a thin host adapter for central-database reads, immutable artifact
publication, and the host's public endpoint shape. Keep the adapter in the host
repository; keep propagation and generic web components here. This preserves a
clean public project while allowing the host to retain private schema and policy.

## Safe migration plan

1. Freeze and export a representative legacy fixture corpus.
2. Implement the host adapter without routing public traffic to it.
3. Run candidate and legacy calculations in parallel.
4. Publish candidate artifacts under a separate version namespace.
5. Run automated API/frontend tests and human map review.
6. Canary a small station group with instant rollback.
7. Expand in stages and monitor errors, latency, and result deltas.
8. Declare the tagged standalone release authoritative.
9. Retain legacy code read-only through the agreed rollback window.
10. Delete legacy implementation only after the window closes successfully.

The publication conclusion and the migration conclusion are therefore
different:

- **Publication:** ready within the documented component scope.
- **Embedding:** supported through a thin adapter.
- **Legacy deletion:** safe only after the host-specific parallel-run gates
  pass, because that operation is irreversible even when both implementations
  are individually correct.
