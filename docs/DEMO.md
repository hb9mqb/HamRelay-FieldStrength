# Street-map demo guide

The reference demo at `/demo/` is a framework-free Leaflet client for the
HamRelay Field Strength HTTP API. It demonstrates the complete browser workflow:
read and edit stations, submit a terrain-aware calculation, follow job status,
display one station or a strongest-field composite, inspect point values, and
download GIS artifacts.

The demo is intentionally small enough to read in full. Its behavior is defined
by [`demo/index.html`](../demo/index.html), [`demo/app.js`](../demo/app.js), and
the [HTTP API](API.md). It is an integration example, not a hardened public
administration console.

> [!WARNING]
> The displayed field is a planning prediction, not measured coverage and not a
> guarantee of communication. The demo is not suitable as a safety-critical
> decision system. Read the [model limitations](MODEL.md) and
> [validation protocol](VALIDATION.md) before operational use.

## First run with HB9ZG

### Prerequisites

The fastest path uses Docker Compose. The first startup and calculation require
network access for the container image or local build, the official ITU-R
P.1812 integral maps, Copernicus DEM tiles, Leaflet assets from `unpkg.com`, and
OpenStreetMap tiles. The calculation service binds to `127.0.0.1:8765` by
default, so it is not exposed on all interfaces.

From the repository root:

```bash
cp .env.example .env
docker compose up -d
curl -fsS http://127.0.0.1:8765/v1/health
```

Use `docker compose up -d --build` when you want to build the image from the
checked-out source. A healthy response is:

```json
{"status":"ok"}
```

Open <http://127.0.0.1:8765/demo/>. The root URL redirects to the same page.
OpenAPI is at <http://127.0.0.1:8765/docs>, and machine-readable feature
discovery is at <http://127.0.0.1:8765/v1/capabilities>.

### What a fresh database contains

On startup, the service seeds [`examples/stations.json`](../examples/stations.json)
only when a station ID is absent. The initial station is **HB9ZG**, the supplied
Rigi-Scheidegg demonstration record:

- coordinates `47.0275, 8.5195833333`, manually verified and locked;
- 439.5375 MHz DMR on 70 cm;
- 25 W ERP;
- 20 m antenna height above local ground; and
- vertical polarization.

The record is marked as a demonstration example that must be verified before
operational use. Seeding never replaces an existing HB9ZG record, so restarting
the service does not undo later registry changes.

### Exact first calculation

1. Wait for the station list to show **HB9ZG**. With a fresh database it is
   selected automatically.
2. Leave **Radius** at **5 km** for the quick test.
3. Leave **Terrain** at **Automatic best available**. Keep the Dataset ID empty.
4. Leave **Visual GeoTIFF** at **Transparent layer**.
5. Keep both **GeoTIFF** and **Web tiles** selected.
6. Press **Calculate selected** once.

The first automatic calculation downloads only the Copernicus tiles needed for
the selected circle and stores them in the persistent DEM cache. GLO-30 is tried
first, with a per-tile GLO-90 fallback when a GLO-30 tile is unavailable. Later
runs reuse cached files.

While work is active:

- the button is disabled, gains a spinner, and reads **Calculating…**;
- radius, terrain, dataset, background, and output controls are disabled;
- the status box receives a moving shimmer, a spinner, and the label
  **PHYSICAL FIELD CALCULATION IN PROGRESS**;
- the status text names the station and its position in the selected sequence;
  and
- the client polls the job endpoint every 1.5 seconds.

The reference API initially reports `queued` and retains that state while the
background calculation is running; the current service does not publish an
intermediate `running` state. At the 5 km default, at least 360 azimuths are
evaluated over the full 360°. Larger radii can increase the ray count to preserve
the configured outer-arc spacing.

On success, the status box displays the terminal job JSON, the calculation
animation stops, the controls are restored, the overlay is added automatically,
and the download targets are updated. Move the pointer inside the calculated
circle to see field and expected receiver values.

## Screen layout

The page has a street map on the left and three control sections on the right.
On viewports narrower than 800 pixels, the map and controls stack vertically.
The map starts at `46.8, 8.2` and zoom level 8.

The background is an attributed OpenStreetMap XYZ layer. It is independent of
the propagation overlay: changing stations, thresholds, or overlay visibility
does not recenter or zoom the map.

The header contains two links:

- **OpenAPI** opens `/docs` in a new tab.
- **Capabilities** opens `/v1/capabilities` in a new tab. This response lists
  the model, input ranges, terrain modes, output formats, backgrounds, palette,
  composite limits, and supported features.

## 1 · Station registry

### Filters and Refresh

The three text fields map directly to exact registry filters:

- **Mode** sends the `mode` query parameter, for example `DMR`.
- **Band** sends `band`, for example `70cm`.
- **Country** sends `country_code`, for example `CH`.

Filters are applied only when **Refresh** is pressed. Empty fields are omitted.
The current demo requests up to the API's default 1,000 records; it does not
provide pagination controls.

Each result row contains a checkbox, station ID, mode, frequency, and the word
`calculated` when `/v1/coverages` contains an artifact for that ID. The map also
shows a marker for every station in the filtered result. A marker popup contains
station ID, TX frequency, and ERP.

Selection is independent of marker display:

- check one station for an individual layer;
- check several stations for sequential calculation and a strongest-field
  composite; or
- clear all selections to disable meaningful overlay and download actions.

On initial load, the client preserves any existing checkbox selection. If there
is none, it selects the first filtered station that already has an artifact, or
otherwise the first station. In a fresh one-record database this is HB9ZG.

### Add or update a station

Expand **Add or update a station** to see the editor. It sends a complete
`PUT /v1/stations/{station_id}` request, not a partial patch.

| Control | API field and behavior |
| --- | --- |
| Admin API key | Sent only as the `X-API-Key` request header |
| Station ID | Path and body identifier; both must match |
| Name | Human-readable registry name |
| Latitude / Longitude | WGS84 decimal degrees |
| TX MHz | Transmit frequency; API range is 30–6,000 MHz |
| ERP W | Effective radiated power, not transmitter output power |
| Antenna AGL m | Antenna height above local ground |
| Mode | Registry filter metadata |
| Band | Registry filter metadata |
| Country | Two- or three-character registry country code |
| Lock coordinates | Preserves coordinates and provenance on later upserts |
| Save station | Validates, upserts, then reloads the station list |

The demo always writes vertical polarization, active status, and `demo editor`
as source and coordinate source. Optional fields not present in the editor use
their schema defaults or `null`. Therefore, saving an existing rich record from
this example editor can replace optional metadata such as RX frequency, antenna
pattern fields, site elevation, source metadata, or `extra`. A production editor
should read, merge, and submit the complete record explicitly.

Coordinate locking is one-way in normal upserts. Once a stored record is locked,
later imports or demo saves preserve its latitude, longitude, coordinate source,
and coordinate precision, even if the submitted checkbox is clear. Other
technical fields can still change. Consequently, the demo cannot move the
seeded, locked HB9ZG coordinate.

Station writes are disabled when the server has no
`FIELD_STRENGTH_ADMIN_API_KEY`; a wrong key returns `401`. The Compose default
placeholder is unsuitable for any shared or public deployment. Set a unique
secret and use TLS before entering it in a browser.

## 2 · Calculate

### Radius

The **Radius** slider spans 1–100 km and defaults to 5 km. The API's exact
accepted interval is greater than 0.25 km and at most 100 km. Runtime grows with
radius because the calculation evaluates more receiver endpoints and can raise
the number of azimuths.

Changing the radius updates the adjacent output label. It does not change an
existing artifact until a new calculation succeeds.

### Terrain

The demo exposes the API's two terrain modes:

- **Automatic best available** sends `terrain_mode: "auto"` and omits a dataset
  ID. The server considers datasets whose declared bounds cover the complete
  calculation circle, orders them by highest priority and then finest declared
  resolution, and can acquire required Copernicus tiles.
- **Named dataset** sends `terrain_mode: "dataset"` and requires the Dataset ID
  field. The identifier must exist in the server-side DEM catalog.

The shipped catalog defines `local-auto-dem` for user-mounted GeoTIFFs and
`copernicus-glo30-auto` for Copernicus acquisition. `local-auto-dem` participates
only when its configured glob resolves to files. The browser can select an ID,
but it can never submit a filesystem path.

The Dataset ID input is disabled in automatic mode and enabled in named mode.
It is also disabled while a calculation is active.

### Visual GeoTIFF

This selector controls the separately rendered RGBA GeoTIFF:

- **Transparent layer** preserves transparency below the chosen minimum and is
  suitable for overlaying in GIS.
- **Street map** composites the field colors over the server-registered
  `streetmap` raster.
- **Map** composites over the server-registered `map` raster.

The selector does **not** change the live Leaflet/OpenStreetMap background. The
repository ships an empty basemap catalog, so `map` and `streetmap` calculations
fail until an operator registers licensed local rasters with attribution. The
service never scrapes live web tiles into a GeoTIFF.

### Output checkboxes

- **GeoTIFF** requests `geotiff`. A successful run publishes the Float32
  analysis GeoTIFF and the selected visual GeoTIFF.
- **Web tiles** sends the API output value `tiles`, which builds the station's
  stored geographic tile pyramid.

At least one checkbox must be selected. The calculation engine always creates
its internal Float32 field artifact; the download API exposes the analysis
GeoTIFF only when `geotiff` is listed as a published output. The Leaflet view
uses the dynamic Web Mercator endpoint, which renders from that field artifact
on request.

### Calculate selected

The button requires one or more checked stations. Multiple stations are
submitted **sequentially** in station-list order. For each station the client:

1. sends `POST /v1/calculations`;
2. polls `GET /v1/calculations/{job_id}` every 1.5 seconds while the status is
   `queued` or `running`;
3. stops on `succeeded` or `failed`; and
4. proceeds to the next station only after success.

After the complete sequence succeeds, the demo replaces the visible overlay and
updates the downloads. A failure stops the sequence and prints the server error
in the status box.

Calculations must be enabled with
`FIELD_STRENGTH_ENABLE_CALCULATIONS=1`. Compose enables them for the loopback
demo. The API itself does not authenticate calculation submission; authentication,
rate limiting, worker isolation, and quotas belong at the deployment boundary.

## 3 · Display and inspect

### The one-overlay lifecycle

The Leaflet demo maintains exactly one propagation `TileLayer` reference:

1. **Show/update** removes the old layer, builds a URL from the current station
   selection and minimum field, and adds one replacement layer.
2. **Hide** removes that layer and clears the reference.
3. Changing station selection automatically replaces the layer only when an
   overlay is currently visible.
4. Changing the minimum field automatically replaces a visible layer.
5. Changing opacity updates the current layer in place.

No part of this lifecycle calls `setView`, `fitBounds`, or another camera
operation. Center and zoom therefore remain unchanged.

With one selected station, the URL is:

```text
/v1/coverage/{station_id}/web-tiles/{z}/{x}/{y}.png
  ?minimum_field_strength_dbuv_m={threshold}
```

With multiple selected stations, the demo creates one server-side composite:

```text
/v1/composites/web-tiles/{z}/{x}/{y}.png
  ?station_ids={comma-separated IDs}
  &minimum_field_strength_dbuv_m={threshold}
  &opacity=1
```

The composite chooses the greatest predicted field in every pixel. It does not
sum signals or model interference. Server opacity is fixed at 1 in the demo so
the Leaflet layer's single opacity control is applied consistently. The API
limits a composite to 64 unique station IDs.

Selecting a station that has not been calculated can produce empty or failed
tile requests. Calculate it first. On a fresh page the client may construct an
overlay URL for the auto-selected HB9ZG before its first artifact exists; seeing
no color at that point is expected.

### Opacity

The **Opacity** slider spans 0–100% and defaults to 70%. It changes only Leaflet
layer alpha:

- 0% makes the layer invisible without removing it;
- 100% shows its rendered alpha at full layer opacity; and
- any intermediate value blends the overlay with the street map.

Opacity does not change field values, the threshold, the manifest, or the
GeoTIFF.

### Minimum field

The **Minimum field** slider spans 0–50 dBµV/m and defaults to 5 dBµV/m. Pixels
below the value become transparent in the requested color tiles. Moving the
slider while the layer is visible builds a new tile URL and replaces the layer;
the stored calculation is unchanged.

This value is a display cutoff, not a measured receiver threshold or a service
guarantee. Choose and label it according to the planning scenario.

### Legend and expected S scale

The legend uses the project-wide absolute palette:

```text
0 purple → 20 blue → 40 cyan → 60 green
         → 80 yellow → 90 orange → 100 red dBµV/m
```

The browser requests `/v1/legend` with the first selected station's frequency,
or 439.5 MHz when none is selected. The response adds the expected S1–S9 field
references for that frequency. In a multi-frequency composite, those reference
labels therefore describe the first selected station, while the color scale
itself remains absolute and station-independent.

Expected S values assume an ideal polarization-matched, lossless 0 dBi antenna
and a matched 50-ohm receiver. They omit real antenna pattern, cable loss,
building penetration, receiver bandwidth, AGC calibration, and local noise.
dBµV/m is the primary quantity.

### Pointer readout and popup

Pointer movement is debounced by 140 ms. After the pointer settles, the demo sends
one `POST /v1/samples` containing all selected station IDs and the WGS84 pointer
coordinate. The server:

1. samples each available station's numerical GeoTIFF;
2. ignores stations whose calculated domain does not contain the point;
3. sorts remaining results by field strength; and
4. returns the strongest result separately.

The text panel shows station ID, dBµV/m, expected S indication, and expected dBm.
The mouse popup shows the same station, a prominent S indication, the field
value, and the `0 dBi / 50 Ω` receiver reference. Leaving the map closes the
popup. If no selected artifact covers the location, the panel says **No
calculated field here.**

Sampling follows the station selection, not the visual layer's opacity. A hidden
overlay can therefore still have calculated values available to the pointer.

### Downloads

The two buttons target the **first selected station**:

- **Analysis GeoTIFF** downloads
  `/v1/coverage/{station_id}/field-strength.tif`;
- **Visual GeoTIFF** downloads
  `/v1/coverage/{station_id}/field-strength-visual.tif`.

The first station is determined by station-list order, not by the most recently
clicked checkbox. There is no composite GeoTIFF download in the demo.

The buttons are selection-driven rather than artifact-discovery-driven: they
become active whenever a station is selected. Before a successful calculation,
or when GeoTIFF was not requested, the server correctly returns `404`. The raw
file is Float32 EPSG:4326 with NoData `-9999`; the visual file is RGBA and must
not be used for numerical analysis. Download the station's
`/v1/coverage/{station_id}/manifest` separately when preserving or sharing the
artifact.

## Troubleshooting

### The service does not become healthy

Inspect the container log:

```bash
docker compose logs -f field-strength
```

At startup, the entrypoint needs `DN50.TXT` and `N050.TXT`. Compose enables
download from the official ITU P.1812-8 archive and records checksums. In an
offline deployment, mount both files under `runtime/itu/` instead. A failed
download, malformed archive, or unwritable runtime volume prevents startup.

### The page loads but the map is blank

The demo loads Leaflet CSS/JavaScript from `unpkg.com` and background tiles from
`tile.openstreetmap.org`. Check browser network errors, content-security policy,
DNS, and egress. The propagation API can be healthy while either third-party
display dependency is unavailable.

### No station appears

Check `GET /v1/stations` and the configured
`FIELD_STRENGTH_DATABASE`/`FIELD_STRENGTH_SEED_STATIONS` paths. Filters are exact
and are applied only after **Refresh**. Clear all three filter fields and refresh
before diagnosing the database.

### Save station returns 401 or 503

- `401 invalid API key` means the entered key does not match
  `FIELD_STRENGTH_ADMIN_API_KEY`.
- `503 station write API is disabled` means that server variable is absent.

Do not place a real key in source code, a URL, or a public screenshot.

### Calculation returns 403

`403 calculation API is disabled` means
`FIELD_STRENGTH_ENABLE_CALCULATIONS` is not enabled. This is the secure default
outside the supplied loopback Compose setup.

### Calculation returns a terrain error

Common causes are:

- no registered dataset covers the complete requested circle;
- a named Dataset ID is unknown;
- a server-side DEM glob resolves to no files;
- Copernicus download failed or the cache is unwritable;
- an input DEM contains NoData along a required azimuth; or
- a configured radio-climate raster is not co-registered or contains values
  other than sea 1, coastal land 3, or inland 4.

Try the 5 km HB9ZG quick test in automatic mode first. Inspect the failed job's
`error` text and container log rather than substituting an arbitrary raster.

### `map` or `streetmap` visual GeoTIFF fails

Those options require a matching entry in
`FIELD_STRENGTH_BASEMAP_CATALOG` and a readable local raster. The shipped
catalog is intentionally empty. Configure licensed data, attribution, and
license metadata, or select **Transparent layer**.

### The job seems stuck at `queued`

The current in-process reference runner does not publish a `running`
transition. First-time DEM acquisition and P.1812 evaluation can be
longer than later cached runs. Watch the container log and resource use. The
job registry is held in memory; restarting the API loses job IDs, although
completed artifacts and the SQLite registry persist in their mounted volumes.

### The overlay is empty

Confirm that:

- the selected station has a successful artifact in `GET /v1/coverages`;
- the map is inside the calculation radius;
- the minimum field is not hiding all visible pixels; and
- the requested tile is not a valid `204 No Content` outside the raster.

Press **Show/update** after correcting selection or threshold. This action does
not move the map.

### Downloads return 404

Calculate the first selected station with **GeoTIFF** checked. The analysis
endpoint is intentionally unavailable when `geotiff` was not published, and the
visual endpoint is unavailable when no visual GeoTIFF was created.

### Docker is not using Metal on Apple silicon

This is expected. Docker Desktop's Linux guest cannot access the host Metal
device. The container uses the CPU/NumPy path. Use the native macOS installation
with the `apple` extra for MLX/Metal interpolation; P.1812 ray evaluation still
runs on CPU performance cores. See [PERFORMANCE.md](PERFORMANCE.md).

## Privacy and security

The default loopback binding is appropriate for local evaluation. Before any
shared deployment:

- terminate TLS at a reverse proxy;
- expose only intended read-only routes publicly;
- authenticate and rate-limit calculations as well as station writes;
- replace the placeholder admin key and rotate it like any credential;
- set explicit `FIELD_STRENGTH_CORS_ORIGINS`;
- isolate calculations from the public API process and enforce CPU, memory,
  concurrency, radius, and storage limits;
- validate artifacts before publication; and
- place immutable artifacts behind an appropriate cache or CDN.

The demo does not store the Admin API key in local storage or source code; it
reads the password field and sends the value in the request header. That does
not make plain HTTP safe outside localhost.

Registry reads expose coordinates and technical station data. Do not insert
private sites into a public registry. Coordinate locking prevents accidental
replacement but does not hide or authorize data.

The browser contacts `unpkg.com` and OpenStreetMap directly, which can disclose
the user's IP address and request metadata to those providers. Review their
privacy and usage policies, retain required attribution, or self-host approved
assets and use a suitable map provider. Terrain, base-map, and ITU products
retain their own licenses; see [DATA-SOURCES.md](DATA-SOURCES.md).

For vulnerability reports, follow [SECURITY.md](../SECURITY.md) rather than
opening a public issue containing credentials or private data.

## Integration lessons from the demo

The reference client illustrates patterns that transfer to React, Vue, Svelte,
server-rendered sites, and native GIS front ends:

1. **Discover before assuming.** Read `/v1/capabilities` for limits and features.
2. **Keep calculation and display separate.** Threshold and opacity should not
   mutate the numerical artifact.
3. **Use the correct tile scheme.** Leaflet uses `/web-tiles`; the bundled Cesium
   controller uses `/tiles` with a geographic tiling scheme.
4. **Preserve camera state.** Layer toggles require no fly-to, zoom, or recenter.
5. **Represent selection exactly.** One station maps to one layer; several map
   to an explicitly labeled strongest-field composite.
6. **Debounce pointer sampling.** The Leaflet demo waits 140 ms and batches up to
   64 stations. The TypeScript Cesium client also cancels superseded requests.
7. **Keep units visible.** Show dBµV/m beside any derived S indication and state
   the receiver assumptions.
8. **Treat the manifest as part of the artifact.** A tile or screenshot without
   model, terrain, station, and sampling provenance is incomplete.
9. **Separate read and write surfaces.** Browsers consume API responses and
   files; they never receive database or server path access.
10. **Plan for durable work execution.** The in-process job runner is a reference
    implementation, not a production queue.

For a Cesium implementation, use the classes in [`web/src`](../web/src/): the
[overlay controller](../web/src/overlay.ts) keeps independent station layers and
camera state, while the [S-meter hover helper](../web/src/smeter.ts) debounces and
cancels requests. Broader deployment and operational examples are in
[PRACTICAL-APPLICATIONS.md](PRACTICAL-APPLICATIONS.md).

## Contributing

Contributions that improve the demo are welcome: accessibility, keyboard and
touch behavior, framework examples, local numerical-tile sampling, clearer job
progress, durable queue integration, offline asset packaging, and tests for
additional browsers are all useful. Scientific or display changes must preserve
the numerical field-strength contract and keep limitations explicit.

Read [CONTRIBUTING.md](../CONTRIBUTING.md), discuss large changes in an issue,
and include tests and documentation. Never add credentials, private station
databases, personal movement traces, licensed DEMs, copyrighted map tiles, or
ITU digital products to a contribution.
