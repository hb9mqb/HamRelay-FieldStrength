# Propagation model

## Normative quantity

The calculator's normative output is median electric field strength in dBµV/m.
It calls the pinned Py1812 implementation of ITU-R P.1812-8 independently for
each radial receiver endpoint. No line-of-sight polygon or color interpolation
is substituted for propagation loss.

Inputs passed to the model are frequency, time percentage, location percentage,
terrain profile, representative clutter height, radio-climatic zone, antenna
heights AGL, polarization, endpoint coordinates, and transmitter ERP. Earth
curvature, diffraction, anomalous propagation and troposcatter are handled by
P.1812; the wrapper does not add a second curvature correction.

At distances below 250 m, the field is:

```text
E[dBµV/m] = 76.92 + 10 log10(ERP[W]) - 20 log10(d[km])
```

This P.525 free-space near-zone branch is needed because a P.1812 terrain
profile requires at least five points and approximately 250 m path length. It
must not be extended across the normal P.1812 domain.

## Sampling and interpolation

The calculation samples complete radial profiles from 0° inclusive to 360°
exclusive. The ray count is:

```text
max(minimum_rays, ceil(2π radius / outer_arc_spacing))
```

P.1812 field endpoints are evaluated along each ray. Bilinear polar
interpolation produces a local azimuthal-equidistant raster, subsequently
reprojected to EPSG:4326. Interpolation does not increase physical model
resolution. The manifest separately records DEM, profile, radial, angular and
output-grid spacing.

## Explicit assumptions

- Actual ERP is used when supplied. The input contract defaults to 12 W only
  when ERP is omitted.
- Radius cannot exceed 100 km.
- Receiver height defaults to 1.5 m AGL.
- Time and location percentages default to 50%.
- A missing radio-climate raster means inland zone 4. Coastal production runs
  should provide a correctly classified zone raster.
- Representative clutter is currently zero. This is explicit in the manifest;
  it is not silently presented as urban accuracy.
- An isotropic antenna pattern is assumed. Directional patterns are a planned
  extension.

## S-meter estimate

For an ideal, polarization-matched, lossless 0 dBi receiving antenna and a
matched 50-ohm receiver, field strength is converted by:

```text
P_r[dBm] = E[dBµV/m] + 20 log10(λ[m]) - 126.755
```

The nominal IARU Region 1 scale uses S9 = −73 dBm below 30 MHz, S9 = −93 dBm
above 30 MHz, and 6 dB per S unit. The UI calls this an *expected indication*.
It is not the primary modeled result and does not claim the calibration of a
particular radio.
