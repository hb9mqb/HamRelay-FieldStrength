# Security policy

## Reporting

Please use GitHub private vulnerability reporting rather than a public issue.
Include affected version, reproduction, impact and any proposed mitigation. Do
not include production credentials, private station datasets or licensed DEMs.

## Scope

Security-sensitive areas include path traversal, malicious rasters, decompression
bombs, calculation denial of service, unbounded radius/workers, artifact cache
poisoning, CORS and unintended activation of calculation endpoints.

The calculation API is disabled by default. If enabled, authenticate and rate
limit it, keep its DEM catalog server-controlled, cap worker and storage quotas,
run calculations outside the public API process, and publish artifacts only
after validation. The public browser should receive files/API responses, never
direct database or filesystem access.
