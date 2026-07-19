# Contributing

Thank you for helping make radio-coverage predictions more transparent and
reproducible. Discussion, measurement data, documentation, test cases and code
are welcome.

## Before a large change

Open an issue describing the physical quantity, use case, assumptions, expected
API impact, validation evidence and licensing. Avoid a large implementation
whose model contract has not been discussed.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ruff check src tests
ruff format --check src tests
cd web && npm ci && npm run check
```

On Apple silicon, add the `apple` extra and include NumPy-versus-Metal numerical
equivalence results. Windows is currently experimental and untested; a first
successful Windows report should include the environment requested in
`docs/WINDOWS.md`.

## Scientific changes

A propagation change must include:

- a primary scientific or standards reference;
- units and valid parameter ranges;
- explicit defaults and uncertainty/limitations;
- deterministic tests and, where relevant, reference profiles;
- artifact/schema compatibility notes; and
- evidence that acceleration does not materially alter numerical output.

Never substitute a visually plausible polygon for actual field strength.
Measured datasets must document calibration, antenna factor, receiver bandwidth,
ERP, route selection, time and licensing. Remove personal location traces that
are not necessary for reproducibility.

## Scientific co-authorship

The project is actively looking for scientific co-authors. A contributor whose
work makes a substantial, high-quality contribution to the research may be
invited to co-author a future revision of the accompanying paper. Relevant work
can include propagation methodology, reproducible software, calibrated field
measurements, validation and statistical analysis, performance research, or
substantive scientific writing.

Authorship is based on the significance and intellectual content of the
contribution, not commit count. A co-author must also review and approve the
final manuscript, help resolve questions about their contribution, and accept
shared responsibility for the integrity of the published work. Smaller but
valuable contributions are acknowledged visibly in release notes and the paper.
Discuss a potential research contribution in an issue early so scope, evidence,
data rights, and expected attribution are clear before significant work begins.

## Pull requests

Keep commits focused, update documentation and the paper when the scientific
contract changes, add a changelog entry, and confirm that no private station
database, internal URL, credential, copyrighted terrain tile or ITU digital map
has entered the diff. By contributing, you agree that your contribution is
licensed under the MIT License.
