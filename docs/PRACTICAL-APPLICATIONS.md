# Practical applications

HamRelay Field Strength turns a registered transmitter and terrain data into a
reproducible, terrain-aware electric-field raster. Its primary output is median
field strength in **dBµV/m**, calculated with the pinned ITU-R P.1812-8
implementation and the documented P.525 short-path branch. That makes the
result useful for planning, comparison, GIS analysis, and open-web maps without
reducing propagation to a decorative or binary footprint.

> [!WARNING]
> **This software is a planning aid, not a safety-critical system and not a
> guarantee of communication.** Never use one prediction as the sole basis for
> emergency coverage, life-safety dispatch, site acceptance, or an operational
> go/no-go decision. Confirm important paths with calibrated measurements,
> exercise the complete radio system, retain independent fallbacks, and apply
> the requirements of the responsible authority.

The [propagation model](MODEL.md), [data requirements](DATA-SOURCES.md), and
[validation protocol](VALIDATION.md) are part of the result's meaning. Keep the
artifact manifest with every raster or tile publication.

## What the system can provide

For each station, the current implementation can provide:

- a Float32 EPSG:4326 GeoTIFF containing field strength in dBµV/m;
- a provenance manifest containing transmitter inputs, model and implementation
  identifiers, sampling geometry, field range, terrain selection, and declared
  assumptions;
- thresholded RGBA tiles for Cesium's geographic tiling scheme and standard XYZ
  Web Mercator clients such as Leaflet;
- stable numerical PNG tiles with a documented 0.5 dB encoding;
- a transparent or background-composited visual GeoTIFF;
- point samples with field strength and an explicitly idealized expected
  receiver level and S-meter indication; and
- strongest-field composites and batch samples for as many as 64 stations.

The threshold and opacity controls are presentation controls. They do not alter
the stored field calculation. A strongest-field composite selects the greatest
predicted value at each pixel; it neither adds fields nor models coherent or
simulcast interaction.

## Amateur-radio operations

### Understanding an existing repeater

A repeater group can publish more useful information than a nominal service
circle or line-of-sight polygon. A field-strength overlay can show, on one
station-independent color scale, where terrain diffraction and longer-path
mechanisms produce strong, marginal, or rapidly changing predictions. Operators
can then:

- inspect valleys, ridges, approach roads, and likely shadow regions;
- compare predictions at known operating locations using the sample API;
- choose a display threshold appropriate to a documented planning scenario;
- explain why two locations at similar range may have very different predicted
  fields; and
- publish the numerical artifact and assumptions instead of only a screenshot.

The expected S indication is useful as a familiar orientation label, but it is
derived for an ideal polarization-matched, lossless 0 dBi antenna and a matched
50-ohm receiver. The field value remains the authoritative result.

### Repeater placement and candidate-site comparison

Candidate sites can be compared defensibly when every scenario uses the same
frequency, ERP convention, receiver height, statistical percentages, terrain
source, radius, and sampling settings. Give every candidate a distinct station
ID, calculate it separately, and preserve each manifest.

A useful review sequence is:

1. verify or survey each candidate coordinate and record its source and
   precision;
2. use realistic ERP and antenna height above local ground, not transmitter
   output power or site elevation as substitutes;
3. calculate all candidates with one controlled DEM selection;
4. compare the individual absolute-color layers at the same threshold;
5. use the composite endpoint only to answer “which candidate is strongest at
   this pixel?”;
6. sample agreed settlements, corridors, and test points; and
7. field-test the short list before procurement or construction.

The registry stores optional antenna azimuth, beamwidth, gain, and downtilt
metadata, but the current propagation engine assumes an isotropic transmitter
pattern and does **not** apply those pattern fields. Do not use the current
result to claim the effect of a directional antenna system.

### Comparing repeaters in a network

Multiple existing repeaters can be selected to build a strongest-field view of
the network. This helps identify areas in which no selected station exceeds a
chosen display threshold and areas in which the modeled best server changes.
Keep the individual station IDs available so a user can inspect the responsible
station rather than treating the composite as a new transmitter.

The batch sample response is particularly suitable for a map popup or planning
table: it returns every intersecting station sorted by field strength and a
separate `strongest` entry. It does not account for channel congestion,
co-channel interference, access tones, digital-network availability, receiver
desensitization, or operational policy.

## Emergency-communications planning

The system can support preparedness work when it is one layer in a wider risk
assessment. Examples include:

- screening assembly points, shelters, hospitals, command posts, and logistics
  routes against a set of existing repeaters;
- identifying locations that deserve a portable relay, cross-band gateway, or
  simplex field test;
- comparing alternate fixed sites before an exercise;
- preparing map products for a tabletop exercise; and
- documenting which modeled assumptions were used for a communications annex.

A responsible workflow separates prediction from readiness:

1. define the operational scenario, frequencies, terminal antenna heights, and
   minimum usable performance before looking at the map;
2. calculate each independent repeater and retain its manifest;
3. inspect both individual layers and a strongest-field composite;
4. export candidate gaps and priority routes to GIS;
5. survey them with calibrated equipment and realistic field antennas;
6. run a live exercise that includes power, backhaul, access control, loading,
   interference, and operator procedures; and
7. maintain simplex, alternate-repeater, portable-relay, and non-radio fallback
   plans.

An adjustable color threshold is not an emergency-service boundary. Buildings,
foliage, vehicles, local clutter, antenna orientation, cable loss, interference,
equipment state, and unusual propagation can move real performance in either
direction. The software contains no availability, resilience, traffic-capacity,
or failure-probability model.

## Drive-test and field-survey validation

Predictions become more useful when they are compared with defensible
measurements. The current API supplies predicted point samples; it does not
ingest, clean, or statistically evaluate drive-test traces. Perform those steps
in a separate analysis tool or GIS so measured and predicted data remain
distinguishable.

### Recommended campaign design

Before collecting data:

- fix the transmitter configuration and document actual ERP, feed-line loss,
  antenna pattern, polarization, and operating state;
- use a calibrated field-strength receiver or a receiver with a documented
  antenna factor and bandwidth;
- record antenna height, cable loss, vehicle effects, GPS position, time, and
  quality flags;
- select routes before inspecting residuals; and
- reserve different routes or time periods for calibration and validation.

During analysis, sample the prediction at each cleaned measurement coordinate
with `GET /v1/coverage/{station_id}/sample` or batch points through an external
script. Preserve the raw observations, the station manifest, and the exact
artifact version. Report bias, mean absolute error, root-mean-square error,
standard deviation, and residual quantiles by distance, terrain class,
visibility state, and field-strength band.

Consumer-radio S meters can support qualitative route checks, but their
readings are not absolute field measurements unless the complete receiving
system has been calibrated. See [VALIDATION.md](VALIDATION.md) before describing
a map as locally validated.

## GIS and desktop analysis

Request the `geotiff` output when the result will be used outside the browser.
Two products have different purposes:

- `field-strength.tif` is the Float32 numerical EPSG:4326 raster. Its NoData
  value is `-9999`; use this file for analysis, contours, zonal statistics,
  sampling, and comparison.
- `field-strength-visual.tif` is an RGBA presentation product. It may be
  transparent or already composited with an operator-provided `map` or
  `streetmap` raster. It is not a numerical substitute.

Always download `manifest.json` with the raster. In a GeoTIFF-capable GIS, keep
the native dBµV/m values, use explicit class boundaries, and label NoData
separately from weak field. A difference raster between controlled candidate
runs can be useful, but it must be produced externally and should not mix runs
with different terrain, sampling, ERP, frequency, or model versions.

The project does not scrape or bundle background maps. Any local base raster
must be registered server-side with its license and attribution. Consult
[DATA-SOURCES.md](DATA-SOURCES.md) before distributing derived map products.

## Public and open-web publication

The API is designed so a public browser can consume artifacts without receiving
database or filesystem access. A public deployment should expose only the
read-only discovery, station-read, manifest, artifact, tile, and sample routes.
Keep station writes and calculation submission behind authentication, strict
rate limits, and resource quotas.

A robust publication layout is:

```text
calculator/worker -> versioned artifact directory -> validation gate
                  -> atomic publication -> read-only API -> cache/CDN -> browser
```

Recommended controls include:

- TLS at the reverse proxy;
- explicit CORS origins rather than a wildcard;
- an unguessable, rotated admin key for station writes;
- authenticated and rate-limited calculation submission;
- CPU, memory, concurrency, radius, and storage quotas;
- immutable caching for numerical tiles and versioned GeoTIFFs;
- shorter caching for threshold-dependent color and composite tiles; and
- atomic artifact validation before a version becomes visible.

The included service uses an in-process reference job registry. Jobs are not
durable across an API restart and calculations run in the API process. Replace
that runner with a durable queue and isolated workers for a multi-user or public
calculation service while preserving the HTTP request contract.

The reference Leaflet demo loads Leaflet from `unpkg.com` and map tiles from
OpenStreetMap. A public operator must comply with those providers' attribution,
usage, caching, privacy, and availability policies or host approved alternatives.

## Concrete API workflows

The complete schema and status behavior are documented in [API.md](API.md).
The following patterns use only implemented endpoints.

### 1. Discover capabilities and stations

Do not hard-code server limits when a client can discover them:

```bash
BASE_URL=http://127.0.0.1:8765
curl -fsS "$BASE_URL/v1/health"
curl -fsS "$BASE_URL/v1/capabilities"
curl -fsS "$BASE_URL/v1/stations?country_code=CH&band=70cm&mode=DMR"
curl -fsS "$BASE_URL/v1/coverages"
```

`GET /v1/stations` also supports status, pagination, and a WGS84 bounding box.
Mode, band, country, and status filters are exact registry values.

### 2. Import a controlled station record

Station writes require the server's `X-API-Key`. Keep the key outside source
code and send it only over TLS:

```bash
curl -fsS -X PUT "$BASE_URL/v1/stations/CANDIDATE-A" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_API_KEY" \
  --data-binary @candidate-a.json
```

Bulk import uses `POST /v1/stations/import` with a `records` array of at most
10,000 complete station records. Once `coordinates_locked` is true, subsequent
upserts preserve latitude, longitude, coordinate source, and coordinate
precision. Other technical fields remain updateable. The lock protects curated
data from imports; it is not an authorization or privacy feature.

### 3. Submit and poll a calculation

```bash
curl -fsS -X POST "$BASE_URL/v1/calculations" \
  -H "Content-Type: application/json" \
  -d '{
    "station_id": "HB9ZG",
    "terrain_mode": "auto",
    "radius_km": 25,
    "output_formats": ["geotiff", "tiles"],
    "geotiff_background": "transparent",
    "minimum_field_strength_dbuv_m": 5
  }'
```

The response is `202 Accepted` with a `job_id`. Poll
`GET /v1/calculations/{job_id}` until the state is `succeeded` or `failed`.
In the current reference runner a job may remain `queued` while the background
task is working. On success, use the station ID to fetch the manifest and
artifacts.

### 4. Add a Leaflet overlay without moving the map

```js
const stationId = "HB9ZG";
const threshold = 5;
const url = `${baseUrl}/v1/coverage/${encodeURIComponent(stationId)}` +
  `/web-tiles/{z}/{x}/{y}.png?minimum_field_strength_dbuv_m=${threshold}`;

const layer = L.tileLayer(url, {
  opacity: 0.7,
  maxZoom: 18,
  noWrap: true,
}).addTo(map);
```

Adding, removing, or replacing the tile layer does not require `setView`,
`fitBounds`, or any other camera mutation. Rebuild the URL when the threshold
changes; update the Leaflet layer opacity directly when only blending changes.

### 5. Request a strongest-field composite

```text
GET /v1/composites/web-tiles/{z}/{x}/{y}.png
    ?station_ids=SITE-A,SITE-B,SITE-C
    &minimum_field_strength_dbuv_m=5
    &opacity=0.7
```

Deduplicate IDs in the client and keep the list at or below 64 stations. Use
`POST /v1/samples` with the same IDs for a pointer popup that identifies the
strongest modeled station and retains all intersecting samples.

### 6. Integrate with Cesium

The package under [`web/`](../web/) supplies `FieldStrengthApi`,
`CoverageOverlayController`, `SMeterHover`, and legend/control helpers. It uses
the geographic tile endpoint, keeps one layer per station, debounces and cancels
superseded hover requests, and deliberately leaves camera position, zoom,
heading, and pitch unchanged. See the [overlay controller](../web/src/overlay.ts)
and [hover implementation](../web/src/smeter.ts).

## Interpretation limits

The current model contract includes several important limits:

- P.1812 is used from 30 MHz to 6 GHz; the service rejects frequencies outside
  that range.
- Calculation radius is limited to 100 km.
- Values below 250 m use the documented P.525 free-space expression.
- Default output uses 50% time and 50% location statistics, a 1.5 m receiver,
  50 m terrain profiles, 200 m radial samples, and a 60 m publication grid.
- The 60 m grid is not a claim of 60 m local predictive accuracy.
- Representative clutter is zero, so buildings, vegetation, and urban clutter
  are not explicitly modeled.
- The transmitter pattern is isotropic in the current engine.
- If no radio-climate raster is configured, paths are treated as inland zone 4;
  that shortcut is unsuitable for defensible coastal work.
- Copernicus GLO-30 is a digital surface model with product- and location-specific
  error, not guaranteed bare-earth terrain.
- The calculation does not model interference, receiver implementation,
  feed-line loss, antenna mismatch, indoor penetration, traffic capacity,
  network backhaul, equipment availability, or operational access rules.
- The expected S value assumes an ideal receiving system and does not assert the
  calibration of a real radio.

Interpolation, higher-resolution rendering, and a finer base map cannot recover
physics absent from the inputs or model. Implementation conformance likewise
does not prove local predictive accuracy.

## Reproducibility checklist

Before sharing or comparing a result, retain:

- station coordinates and their provenance;
- frequency, actual ERP, antenna AGL height, and polarization;
- DEM product, version, checksums, CRS, vertical datum, NoData treatment, and
  license;
- radio-climate data or the explicit inland-only assumption;
- radius and all profile, radial, angular, and output-grid settings;
- model, implementation, algorithm, and raster-backend identifiers;
- the unmodified numerical GeoTIFF and manifest; and
- a description of any display threshold, palette, or base map applied later.

For scientific use, follow the repository's [citation metadata](../CITATION.cff)
and accompanying [paper](../paper/paper.pdf).

## Contributing practical evidence

Contributions are welcome, especially calibrated field surveys, independent
conformance cases, reproducible site-comparison studies, radio-climate and
clutter adapters, uncertainty displays, GIS workflows, accessibility work, and
portable performance results. Measurement contributions must document
calibration, antenna factors, receiver bandwidth, ERP, route selection, time,
licensing, and privacy treatment.

Read [CONTRIBUTING.md](../CONTRIBUTING.md) before a large change and use the
[security policy](../SECURITY.md) for vulnerabilities. Remove unnecessary
personal movement traces, private station records, credentials, licensed
rasters, and internal URLs before opening an issue or pull request.
