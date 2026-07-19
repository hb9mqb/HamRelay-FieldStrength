# Troubleshooting

Start with the smallest observable boundary: service health, capabilities,
station record, calculation status, manifest, one tile, and finally the map.

## Browser reports `NetworkError` or connection refused

```bash
docker compose ps
docker compose logs --tail=200 field-strength
curl -v http://127.0.0.1:8765/v1/health
```

Confirm the published port, firewall, reverse-proxy target, and browser origin.
The default Compose binding is loopback-only. A different device cannot reach
`127.0.0.1` on your machine. For public use, bind through a TLS reverse proxy
and configure exact CORS origins instead of exposing the database or container
port directly.

## Calculation returns `403`

`FIELD_STRENGTH_ENABLE_CALCULATIONS` is disabled. This is the safe default for a
read-only deployment. Enable it only on an authenticated, resource-limited
calculation service.

## Calculation returns `no registered DEM covers...`

The selected catalog entry must cover the complete analysis circle, not only
the transmitter point. Check catalog bounds, radius, mounted paths, glob
patterns, and file readability inside the container. In automatic mode, verify
that the DEM cache volume is writable.

## Calculation fails with terrain NoData

A profile crossed a missing DEM cell. Confirm that all required source tiles
were acquired and co-register correctly. Inspect the manifest/acquisition
metadata and retry after repairing the cache. Do not silently replace NoData
with zero elevation; that creates physically false paths.

## The overlay is absent but markers are visible

Markers and propagation artifacts are independent. Check in order:

1. `/v1/coverages` includes the station;
2. `/v1/coverage/{id}/manifest` returns 200;
3. the map uses `/tiles/` for Cesium or `/web-tiles/` for Leaflet;
4. a known intersecting tile returns PNG rather than 204/404;
5. the minimum field threshold is not hiding all pixels;
6. layer opacity is above zero; and
7. the station identifier is URL-encoded exactly once.

A `204` response is valid when the requested tile does not intersect calculated
pixels. Do not treat it as a corrupt image.

## The map is blue, white, or blank

Open browser developer tools and inspect console/network errors. Common causes
are a blocked base-map provider, mixed HTTP/HTTPS content, incorrect CORS,
missing Cesium assets, a failed reverse proxy, or a script exception before map
initialization. Test `/v1/health` and the demo from the same browser origin.

The base map and overlay are separate. A base-map failure should not be diagnosed
as a propagation error until a direct overlay tile has also failed.

## Overlay colors appear uniform

Inspect field minima/maxima in the manifest and sample several locations. The
absolute palette must not be normalized independently for each station. A high
display floor can leave only one narrow color interval; return the threshold to
5 dBµV/m. If numeric samples vary but rendered colors do not, check value-tile
encoding and the palette lookup rather than recalculating the physical field.

## S-meter popup does not appear

Ensure at least one calculated station is selected and visible. Test
`/v1/coverage/{id}/sample` or `POST /v1/samples` at a coordinate inside the
artifact bounds. The browser handler debounces movement and aborts superseded
requests; persistent errors normally indicate CORS, an invalid station ID, or a
point outside every raster.

## The demo keeps old overlays

The reference demo intentionally owns exactly one Leaflet propagation layer.
`Show/update`, selection changes, and threshold changes remove the previous
instance before adding its replacement. If multiple layers remain after custom
integration, retain the layer handle and call the map library's removal method
before creating the next one.

## Coordinate edits disappear after import

Set `coordinates_locked=true` on the authoritative station record. The bundled
upsert preserves locked latitude, longitude, coordinate source, and precision.
If a host application synchronizes records, it must enforce the same rule before
calling this service.

## Docker build or startup cannot download dependencies

Verify DNS, proxy settings, CA certificates, and access to the pinned Python and
ITU sources. For reproducible offline deployment, build and scan the image in a
connected environment, mirror permitted dependencies, and transfer an immutable
image digest. Do not commit downloaded licensed products into this repository.

## Windows problems

Windows support is experimental and untested. Use the diagnostic checklist in
[WINDOWS.md](WINDOWS.md) and report Python, architecture, GDAL/Rasterio versions,
process start method, traceback, and a minimal non-private fixture.

## Reporting a bug

Include the release/commit, platform, sanitized station inputs, radius, DEM
source/version, manifest, exact endpoint/command, traceback or HTTP status, and
whether NumPy or Metal rasterization was used. Never attach credentials, private
station databases, or terrain files whose license forbids redistribution.
