# Data sources and provenance

The software does not bundle terrain, land-cover, map imagery, or ITU digital
products. Operators must obtain them under their original terms and retain a
machine-readable source record.

## Terrain

Copernicus DEM GLO-30 is a practical worldwide default. It is a digital surface
model derived primarily from TanDEM-X data, has one-arc-second latitude spacing,
uses EGM2008 vertical heights, and reports global aggregate accuracy rather than
a guarantee at each location. Buildings and vegetation may be represented in
the surface. Use the official Product Handbook and attribution notice.

Regional bare-earth DTMs may improve terrain profiles when their vertical datum,
sampling, coverage, and license are known. A finer input does not by itself make
P.1812 predict individual buildings or indoor reception.

For each run, record at least:

- product name, edition, acquisition period and download URL;
- license and required attribution;
- SHA-256 checksums of input tiles;
- horizontal CRS and vertical datum;
- native post spacing, resampling method and NoData handling; and
- any mosaicking, void filling or datum transformation.

## Radio-climatic zones

P.1812 uses sea (1), coastal land (3), and inland (4) classifications. Coastline
classification affects anomalous-propagation terms and terminal coast distance.
If a zone raster is omitted, this implementation records an inland-only
assumption. Do not use that shortcut for defensible coastal predictions.

## ITU digital products

Py1812 requires `DN50.TXT` and `N050.TXT` distributed with Recommendation
ITU-R P.1812-8. They are integral ITU products and are deliberately excluded
from this repository. Follow ITU and Py1812 redistribution rules.

## Third-party licenses

The repository's MIT License applies only to original project code and
documentation. Py1812 has its own acknowledgement and modification terms;
Copernicus DEM and other data have separate licenses. Review all terms before
redistribution or a hosted service launch.
