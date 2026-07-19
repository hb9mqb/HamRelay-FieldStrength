# Release process

This process is for project maintainers. It keeps software versions, scientific
claims, API contracts, container artifacts, citation metadata, and release notes
aligned. A release is not ready merely because it builds.

## One-time public repository setup

Before the first release, a repository administrator should:

- enable Issues and GitHub private vulnerability reporting;
- enable Dependabot alerts, dependency-graph updates, and security updates;
- allow GitHub Actions to publish packages using the repository token;
- protect `main`, require pull requests, dismiss stale approvals after material
  changes, and require the stable `CI / Required checks` status plus the
  container build where appropriate;
- protect release tags matching `v*` from deletion or rewriting;
- create and consistently apply `breaking-change`, `science`, `validation`,
  `enhancement`, `bug`, `documentation`, `dependencies`, and `skip-changelog`
  labels used by the generated-release-notes configuration; and
- verify that the published GHCR package has the intended public visibility and
  repository linkage.

Keep write access small and use individual accounts with multi-factor
authentication. Do not store long-lived publication tokens in the repository;
prefer scoped repository tokens and trusted publishing when a future package
registry workflow is reviewed.

## Release scope and versioning

Use Semantic Versioning for the software contract:

- **Patch** releases correct compatible implementation or documentation defects.
- **Minor** releases add backward-compatible API, artifact, model, or integration
  capabilities.
- **Major** releases may change public APIs, database/artifact schemas, numerical
  semantics, defaults, units, palette interpretation, or other behavior on which
  users rely.

A scientifically meaningful change can require a major release even when the
Python signature is unchanged. In particular, treat changes to the propagation
recommendation, field quantity, reference conditions, ERP interpretation,
clutter/terrain semantics, S-meter conversion, default antenna assumptions, or
color thresholds as public-contract changes. State whether existing coverage
artifacts must be recalculated.

## 1. Prepare the candidate

Work from a dedicated release branch or pull request based on current `main`.
Confirm that the checkout and remote point to the intended public repository
before pushing anything.

Update and cross-check:

- `pyproject.toml` package version;
- `CITATION.cff` software version and release date;
- `CHANGELOG.md`, moving relevant Unreleased entries into the dated release;
- API/model/data-source/performance/validation/platform documentation;
- the scientific paper and references when scientific claims change;
- database migrations and artifact/schema compatibility notes; and
- example requests, demo behavior, screenshots, and sample station data.

Do not introduce private station data, internal service URLs, secrets, personal
location histories, copyrighted basemap tiles, restricted DEMs, or official ITU
digital-map files. Record provenance and licenses for every new dependency,
dataset, image, and copied excerpt.

## 2. Validate source and interfaces

Create an isolated environment with a supported Python release and run the same
checks as CI:

```bash
export RELEASE_ENV_DIR="$(mktemp -d)"
python -m venv "${RELEASE_ENV_DIR}/venv"
source "${RELEASE_ENV_DIR}/venv/bin/activate"
python -m pip install --upgrade pip build twine
python -m pip install -e '.[dev]'
python -m ruff check src tests docker
python -m ruff format --check src tests docker
python -m pytest

cd web
npm ci
npm run check
npm run build
node --check ../demo/app.js
cd ..

python -m build
python -m twine check dist/*
```

Also compile the paper from a clean LaTeX environment and visually inspect every
page of the resulting PDF. Confirm citations, equations, units, figure captions,
links, author names, and page layout.

## 3. Validate the scientific result

For every numerical-model change:

1. Run deterministic reference profiles spanning line of sight, diffraction,
   terrain obstruction, short paths, maximum radius, and NoData edges.
2. Compare against the pinned reference implementation or independently
   reproduced standard cases, and record tolerances.
3. Compare NumPy and Metal/MLX output on the same inputs; quantify all residuals.
4. Test the 12 W fallback separately from an explicitly supplied actual ERP.
5. Verify dBµV/m values, GeoTIFF samples, web-tile samples, composite maxima,
   threshold behavior, legend labels, and S-meter conversion agree.
6. Document validation limitations rather than presenting visual plausibility as
   physical validation.

Where calibrated measurements are available, preserve a machine-readable record
of calibration, antenna factor/gain and height, feeder loss, bandwidth/detector,
route/time, aggregation, uncertainty, data license, software commit, and terrain
version. A visually attractive overlay is never sufficient evidence by itself.

## 4. Validate the container and demo

Build the same application definition used for the quick start. Use a unique
Compose project name so the release check cannot collide with another local
deployment:

```bash
export FIELD_STRENGTH_PORT=18765
export FIELD_STRENGTH_ADMIN_API_KEY=release-check-local-only
docker compose --project-name hamrelay-release-check up --build --detach
curl --fail --retry 30 --retry-delay 2 http://127.0.0.1:18765/v1/health
```

Open `http://127.0.0.1:18765/demo/` in a clean browser profile. Starting from the
bundled example station, verify that a user can press **Calculate selected** and
obtain a colored field-strength overlay without manually entering seed data.
Check the progress indicator, single-overlay lifecycle, opacity and minimum-field
controls, dBµV/m/S-meter legend, cursor popup, street-map attribution, GeoTIFF
links, error messages, and keyboard operation.

Stop the isolated smoke-test project after inspection:

```bash
docker compose --project-name hamrelay-release-check down
```

Test at least one native Apple-silicon run for a release that claims Metal/MLX
support. Windows remains experimental until a documented native validation run
has been completed; do not infer support solely from a passing emulated or
cross-platform build.

## 5. Security and operational review

- Confirm calculation endpoints remain opt-in and administrative writes require
  authentication.
- Test radius, worker, raster-size, storage, and request validation limits.
- Review CORS defaults, filesystem paths, archive/raster parsing, cache keys, and
  artifact publication boundaries.
- Scan the complete Git history and built container for secrets and internal
  URLs, not only the final diff.
- Review dependency changes and container base-image findings. Document accepted
  residual risk; do not silently waive a relevant high-severity finding.
- Confirm the public API never exposes direct database or filesystem access.

Use private vulnerability reporting for any issue discovered during this review.

## 6. Approve, tag, and publish

Require a green protected-branch build. Seek independent review for scientific,
security-sensitive, or breaking changes. If an initial solo-maintainer release
cannot receive independent review, state that limitation in the release notes
and keep all evidence public for subsequent review. Merge the release pull
request, then verify the repository, branch, remote, and clean working tree
before creating an annotated, preferably signed tag:

```bash
export RELEASE_VERSION=0.1.0
git status --short
git rev-parse --show-toplevel
git branch --show-current
git remote -v
git tag --sign "v${RELEASE_VERSION}" -m "HamRelay Field Strength ${RELEASE_VERSION}"
git push origin "v${RELEASE_VERSION}"
```

If signed tags are not configured, document the maintainer identity check and
use an annotated tag; never create an unsigned lightweight tag accidentally.
Never move or overwrite a published release tag. Correct a bad public release
with a new version and an explicit advisory.

The tag starts the container workflow. Wait for all architecture builds to
finish, then inspect the published image manifest, immutable digest, provenance,
and SBOM. GitHub provides source archives automatically; attach only artifacts
that were produced from the tagged commit and whose licenses permit
redistribution. Do not publish to PyPI until a separately reviewed trusted
publishing workflow and package ownership are in place.

## 7. Write release notes

Generated notes are a starting point, not the finished scientific record. Add:

- a concise practical summary and intended users;
- model, assumptions, defaults, units, and validation changes;
- API, database, artifact, demo, and deployment changes;
- recalculation or migration requirements;
- measured performance with exact hardware/software context;
- known limitations, especially experimental platforms;
- security-impacting changes and upgrade urgency;
- contributor acknowledgements; and
- the container digest and citation guidance.

Do not claim accuracy, hardware performance, compatibility, or operating-system
support that was not tested for this exact candidate.

## 8. Authorship and contributor credit

Credit all substantive work in release notes. If a release changes the paper,
apply the authorship criteria in `CONTRIBUTING.md` before final manuscript
approval. Prospective co-authors must have made a substantial intellectual
contribution, review and approve the manuscript, help resolve questions about
their work, and accept shared responsibility for the paper's integrity. Record
contributor roles and obtain explicit consent before adding a name to the paper
or citation metadata.

Valuable contributions that do not meet authorship criteria still receive clear
acknowledgement. Never exchange authorship for funding, status, or routine work.

## 9. Post-release verification

From a clean machine or environment:

1. Pull the immutable container digest and repeat the health/demo smoke test.
2. Install the source artifact and verify package metadata and CLI startup.
3. Open every documentation and citation link on the public release page.
4. Confirm the release notes, tag, container labels, paper, and API version agree.
5. Start a new Unreleased section in the changelog for subsequent work.

If a serious defect appears, disclose it promptly, describe safe mitigations,
and prepare a patch release. Never delete or quietly replace released scientific
artifacts.
