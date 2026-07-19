# Validation protocol

Validation has three distinct layers.

## 1. Formula and encoding tests

Unit tests cover P.525 reference values, field-to-power conversion, nominal
S-meter boundaries, palette endpoints, NoData, numerical-tile round trips and
geographic tile bounds.

## 2. Implementation conformance

Run Py1812's published validation profiles at the pinned revision and compare
basic transmission loss and field strength within the upstream tolerance. Add
golden rasters for flat terrain, a single ridge, sea/coastal/inland transitions,
and azimuth wraparound. Compare NumPy and Metal interpolation with declared
absolute and relative tolerances.

Conformance proves that code implements the selected recommendation; it does
not prove local predictive accuracy.

## 3. Empirical field validation

A defensible campaign should use calibrated equipment, known antenna factors,
GPS time and location, fixed transmitter ERP, feed-line and antenna-pattern
records, and routes selected before residual inspection. Preserve raw samples.
Separate calibration and validation routes. Report bias, MAE, RMSE, standard
deviation and quantiles by distance, terrain class, line-of-sight state and
field-strength band.

Avoid presenting S-meter readings from uncalibrated consumer radios as absolute
field measurements. They can support qualitative checks but not replace a
calibrated field-strength receiver.
