# Embedded station database

The API initializes its SQLite database automatically. The default development
path is `database/stations.sqlite3`; Docker stores the same schema in the
persistent `/database` volume.

The registry contains transmitter coordinates, coordinate-lock metadata,
frequency, ERP, antenna height and pattern parameters, operating mode, source
provenance, status, extensible JSON metadata, and the current coverage-artifact
reference. Runtime database files are intentionally excluded from Git.

Use `PUT /v1/stations/{station_id}` for one record or
`POST /v1/stations/import` for a validated bulk import. Both endpoints require
the `X-API-Key` configured by `FIELD_STRENGTH_ADMIN_API_KEY`. Once a record has
`coordinates_locked=true`, later imports cannot overwrite its coordinates or
coordinate provenance.
