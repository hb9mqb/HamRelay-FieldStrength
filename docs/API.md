# HTTP API

The FastAPI service combines a station registry, an opt-in calculation runner,
artifact delivery, map tiles, composites, and point sampling. Calculations are
disabled by default and the database must never be exposed directly to a public
browser. The HTTP layer is the security and validation boundary: it accepts a
radius and one of two terrain-selection modes but never client-controlled paths.
Interactive OpenAPI documentation is exposed at `/docs`; the machine-readable
schema is `/openapi.json`. The complete Leaflet reference client is mounted at
`/demo/`, and `/` redirects there.

## Discovery and station registry

`GET /v1/capabilities` reports model, units, supported input ranges, output
formats, terrain modes, backgrounds, composite limits, palette, and optional
features. `GET /v1/legend?frequency_mhz=439.5` returns the absolute palette and
the frequency-dependent expected S1–S9 reference.

`GET /v1/stations` supports `mode`, `band`, `country_code`, `status`, pagination,
and an optional WGS84 bounding box (`west`, `south`, `east`, `north`).
`GET /v1/stations/{station_id}` returns one record.

Authenticated writes use `X-API-Key`, whose server value is configured by
`FIELD_STRENGTH_ADMIN_API_KEY`:

- `PUT /v1/stations/{station_id}` validates and upserts one complete record;
- `POST /v1/stations/import` validates and upserts up to 10,000 records.

The schema stores coordinates and provenance, a manual coordinate lock, site
and antenna heights, TX/RX frequencies, ERP, polarization, optional antenna
pattern parameters, mode, band, status, source metadata, and extensible JSON.
Once `coordinates_locked` is true, later imports preserve coordinates,
coordinate source, and precision. Other technical values remain updateable.

## Artifact layout

```text
FIELD_STRENGTH_ARTIFACT_ROOT/
└── TEST-UHF-001/
    ├── manifest.json
    └── field-strength.tif
```

`station_id` accepts alphanumerics, `_`, and `-`. Traversal and absolute paths
are rejected.

## Endpoints

### `POST /v1/calculations`

Disabled unless `FIELD_STRENGTH_ENABLE_CALCULATIONS=1`. The client supplies
exactly one of an inline `station` or registered `station_id`, plus `radius_km` in the interval
`(0.25, 100]`. `output_formats` accepts `geotiff`, `tiles`, or both. The
response is `202 Accepted` with a job ID. Poll
`GET /v1/calculations/{job_id}` for `queued`, `succeeded`, or `failed`.

Terrain has exactly two modes:

- `dataset`: `dem_dataset_id` is required and selects one registered source.
- `auto`: `dem_dataset_id` is omitted. The server selects among sources whose
  declared bounds cover the complete analysis circle, ordered by priority and
  then finest declared resolution.

```json
{
  "station_id": "TEST-UHF-001",
  "terrain_mode": "auto",
  "radius_km": 75,
  "output_formats": ["geotiff", "tiles"],
  "geotiff_background": "transparent",
  "minimum_field_strength_dbuv_m": 5
}
```

Inline station objects use `id`, WGS84 latitude/longitude, MHz frequency, ERP,
AGL antenna height, and polarization. For automatic selection use
`"terrain_mode":"auto"` and omit `dem_dataset_id`. The reference deployment
downloads required Copernicus GLO-30 tiles into its persistent cache and falls
back per tile to GLO-90 when necessary. The manifest records requested mode,
selected dataset, acquisition provenance, and checksums.

`FIELD_STRENGTH_DEM_CATALOG` points to a server-side JSON object whose entries
contain bounds, resolution, priority, source, `dem_paths`, and optionally
`radio_climate_path`:

```json
{
  "copernicus-glo30-global-2022": {
    "source": "Copernicus DEM GLO-30, 2022",
    "bounds": [-180, -90, 180, 90],
    "resolution_m": 30,
    "priority": 10,
    "dem_paths": ["/srv/dem/copernicus/*.tif"]
  }
}
```

Server catalog paths may contain server-controlled globs; clients can never
submit paths. Production deployments
should replace the in-process reference job runner with a durable queue while
retaining this request contract.

### `GET /v1/health`

Returns `{"status":"ok"}`. It does not assert that every artifact is present.

### `GET /v1/coverage/{station_id}/manifest`

Returns immutable provenance, station inputs, physical units, sample spacing,
field range, model revision, and declared assumptions. A missing artifact is
`404`.

### `GET /v1/coverage/{station_id}/field-strength.tif`

Downloads the Float32 EPSG:4326 GeoTIFF if `geotiff` was requested. NoData is
`-9999`; band tags include `units=dBµV/m`, model and pinned implementation.
`404` means the format was not selected. Clients should preserve the companion
manifest when redistributing or analyzing the raster.

### `GET /v1/coverage/{station_id}/field-strength-visual.tif`

Each requested GeoTIFF calculation also creates a visual RGBA GeoTIFF. Its
`geotiff_background` is one of:

- `transparent` (default): NoData and values below the selected threshold are
  transparent, suitable as a GIS layer;
- `map`: embeds a server-registered general map raster; or
- `streetmap`: embeds a server-registered street-map raster.

The visual file is not a numerical substitute for `field-strength.tif`.
`FIELD_STRENGTH_BASEMAP_CATALOG` points to licensed local background rasters:

```json
{
  "map": {
    "raster_path": "/srv/basemaps/map.tif",
    "attribution": "Required provider attribution",
    "license": "Provider license identifier"
  },
  "streetmap": {
    "raster_path": "/srv/basemaps/streetmap.tif",
    "attribution": "Required provider attribution",
    "license": "Provider license identifier"
  }
}
```

The service does not scrape or silently embed third-party web tiles.
Attribution and license are retained in the manifest and GeoTIFF tags.

### `GET /v1/coverage/{station_id}/tiles/{z}/{x}/{y}.png`

Returns an RGBA tile using Cesium's geographic pyramid (level 0 is 2×1; Y runs
north to south). Query parameter:

- `minimum_field_strength_dbuv_m`: float from 0 to 50, default 5. Pixels below
  it are transparent. The stored field is unchanged.

Response `204` means no calculated pixels intersect the tile. Dynamic color
tiles use `Cache-Control: public, max-age=3600` because the threshold is part of
the cache key.

### `GET /v1/coverage/{station_id}/web-tiles/{z}/{x}/{y}.png`

Returns the equivalent dynamic RGBA overlay in the standard XYZ Web Mercator
scheme used by Leaflet and most street-map clients. It accepts the same
`minimum_field_strength_dbuv_m` parameter. Adding or removing the layer does not
change map center or zoom.

### Composite tiles

`GET /v1/composites/tiles/{z}/{x}/{y}.png` uses the Cesium geographic scheme;
`GET /v1/composites/web-tiles/{z}/{x}/{y}.png` uses Web Mercator. Supply a
comma-separated `station_ids` query parameter with at most 64 IDs, plus optional
`minimum_field_strength_dbuv_m` and `opacity`. Each pixel uses the highest
predicted field among the requested stations. The operation does not add fields
or imply simulcast coherence.

### `GET /v1/coverage/{station_id}/values/{z}/{x}/{y}.png`

Returns a single-channel PNG. Zero is NoData. Values 1–255 decode as:

```text
E[dBµV/m] = -20 + (value - 1) × 0.5
```

Numerical tiles are immutable for a given artifact version and carry a one-year
cache directive. Clients should use them for composites and local cursor
sampling when network latency matters.

### `GET /v1/coverage/{station_id}/sample`

Required query parameters are `latitude_deg` and `longitude_deg`.

```json
{
  "station_id": "TEST-UHF-001",
  "latitude_deg": 46.81,
  "longitude_deg": 8.21,
  "field_strength_dbuv_m": 38.42,
  "expected_receiver_dbm": -96.91,
  "expected_s_meter": "S8",
  "receiver_reference": "ideal matched 0 dBi antenna; local losses excluded"
}
```

The endpoint returns `404` when the coordinate is outside the calculated
domain. Consumer code should debounce pointer movement and cancel superseded
requests, as the included TypeScript client does.

`POST /v1/samples` accepts up to 64 `station_ids` and one WGS84 coordinate. It
returns all intersecting samples sorted by field strength and a `strongest`
entry. This is the efficient hover endpoint for a filtered multi-station map.

## Reference street-map demo

The `/demo/` client uses Leaflet and an attributed OpenStreetMap background. It
is deliberately framework-free so its integration patterns can be copied into
React, Vue, Svelte, or server-rendered sites. It demonstrates:

- registry filters and authenticated station editing;
- auto or named terrain selection and a 1–100 km radius control;
- output format and visual GeoTIFF background selection;
- calculation submission and job polling;
- independent or strongest-field composite Web Mercator layers;
- live opacity and 0–50 dBµV/m threshold controls;
- absolute field legend and frequency-dependent S references;
- debounced multi-station pointer inspection; and
- numerical and visual GeoTIFF downloads.

The street-map provider remains independent of the transparent propagation
overlay. A deployment must follow its tile policy, attribution, caching, and
license requirements.

## Deployment

Terminate TLS at a reverse proxy. A public read-only deployment should allow
only discovery, station-read, artifact, tile, and sample routes; keep station
writes and calculations behind authentication and stricter rate limits. Enable
CORS only for intended origins and place tiles behind a CDN.
Artifact publication should be atomic: write a new directory, validate it, then
swap a versioned pointer. Keep calculation credentials and DEM storage outside
the public service.
