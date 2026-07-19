# Support

HamRelay Field Strength is an open-source research and engineering project. The
best support request is reproducible, safe to discuss in public, and useful to
the next person with the same question.

## Start here

Before opening an issue:

1. Follow the README quick start exactly and verify `/v1/health`.
2. Reproduce the behavior with the included demo before adapting it to another
   website.
3. Check the [API documentation](docs/API.md), [model contract](docs/MODEL.md),
   [data-source notes](docs/DATA-SOURCES.md),
   [validation guide](docs/VALIDATION.md), [performance notes](docs/PERFORMANCE.md),
   [Windows status](docs/WINDOWS.md), and existing issues.
4. Retry against the latest released version. If you test the development
   branch, record the complete commit SHA.
5. Reduce the case to one station and the smallest practical radius while
   preserving the problem.

## Choose the right public form

- Use **Bug report** for reproducible incorrect software behavior.
- Use **Scientific or model validation** for measurements, reference cases, or
  technically supported disagreements with a prediction.
- Use **Feature request** for a new capability or a changed contract.
- Use **Integration or usage question** for the demo, API, Docker, terrain
  configuration, GeoTIFFs, tiles, or website integration.

Support is provided by maintainers and volunteers as time permits. Opening an
issue does not create a service-level commitment. Clear reports with minimal
examples, exact versions, explicit units, and lawful reproduction data are much
more likely to receive a useful answer.

## Information that usually matters

For software or deployment questions, include:

- release, commit, or immutable container digest;
- installation method, operating system, architecture, and Python/browser
  versions;
- exact sanitized request, command, and response;
- whether Metal/MLX acceleration was enabled; and
- the smallest relevant log excerpt.

For propagation questions, also include frequency, actual ERP (or explicitly
identify the 12 W fallback), transmitting and receiving antenna heights, radius,
ray count, working-grid spacing, terrain source/version/resolution, output mode,
coordinates or a privacy-safe reference case, and all compared values with
units. Measurement comparisons need instrument calibration, antenna factor or
gain, feeder loss, receiver bandwidth/detector, sampling method, time, and an
uncertainty estimate.

The output is a terrain-aware downlink field-strength prediction, not a promise
of a successful two-way radio link. Receiver performance, local clutter,
building penetration, interference, antenna orientation, feeder loss, uplink
conditions, and time variability can all change practical results.

## Safety and service expectations

Do not use a prediction from this project as the sole basis for emergency,
life-safety, aviation, maritime, or regulatory decisions. Validate critical
coverage with qualified engineering review and calibrated field measurements.
Users remain responsible for lawful frequency use, transmitter power, data
licenses, and basemap attribution in their jurisdiction.

## Public-data boundaries

Never post API keys, passwords, tokens, private station databases, personal
movement traces, internal URLs, or data you cannot redistribute. Official ITU
digital maps and some terrain/basemap products have license conditions; describe
how to obtain them instead of attaching restricted copies. Sanitize logs and
requests before submission.

## Security vulnerabilities

Do not open a public issue for a suspected vulnerability. Follow
[SECURITY.md](SECURITY.md) and use GitHub private vulnerability reporting. This
includes authentication bypass, malicious-raster handling, path traversal,
calculation denial of service, cache poisoning, unsafe CORS behavior, or
credential exposure.

## Professional and research collaboration

Contributions are welcome in propagation science, calibrated field measurement,
statistical validation, performance engineering, additional compute backends,
cross-platform support, web integration, accessibility, documentation, and
translation. Start with the feature or validation form and describe what you can
contribute.

Meaningful work is credited in release notes and, where appropriate, the paper.
The project is also seeking scientific co-authors. Substantial, high-quality
intellectual contributions may be considered under the transparent authorship
criteria in [CONTRIBUTING.md](CONTRIBUTING.md); authorship is not awarded merely
for opening issues or accumulating commits.
