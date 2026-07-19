## Summary

Describe the problem and the outcome of this change. Link the design or issue
discussion with `Closes #…` where appropriate.

## Change type

- [ ] Bug fix
- [ ] Feature or API change
- [ ] Scientific model or validation change
- [ ] Performance or compute-backend change
- [ ] Demo, browser integration, or user-experience change
- [ ] Documentation, paper, or maintenance change

## Scientific and compatibility impact

State what physical quantity, assumptions, units, defaults, validity range, and
uncertainty are affected. Describe API/schema/artifact compatibility and migration
needs. Write **Not applicable** only when the change cannot affect calculations or
their interpretation.

## Evidence

List the exact checks you ran and summarize their results. For numerical changes,
include reference cases, tolerances, and NumPy-versus-accelerated equivalence where
relevant. Add before/after screenshots for visible demo or overlay changes.

```text
pytest ...
ruff check ...
npm ...
```

## Review checklist

- [ ] The change is focused and linked to prior discussion when it changes the scientific or API contract.
- [ ] Tests cover new behavior and important failure modes.
- [ ] Units, ranges, defaults, assumptions, uncertainty, and limitations are explicit where relevant.
- [ ] Acceleration does not silently change numerical results, or the difference is quantified and justified.
- [ ] Public API/schema/artifact changes are documented and compatibility is addressed.
- [ ] The demo and integration examples remain understandable, keyboard-usable, and safe to expose publicly.
- [ ] Documentation, the scientific paper, citation metadata, and changelog were updated where applicable.
- [ ] No credential, private station database, internal URL, personal trace, licensed ITU map, restricted DEM, or other non-redistributable material is included.
- [ ] New dependencies and copied material have compatible licenses and recorded provenance.
- [ ] I ran the relevant local checks, or clearly explained why a check could not run.
- [ ] I agree that this contribution is submitted under the repository's MIT License and will follow the Code of Conduct.

High-quality contributions are recognized publicly. Substantial intellectual work
may be considered for scientific co-authorship under the criteria in
[CONTRIBUTING.md](../CONTRIBUTING.md); a pull request does not itself guarantee
authorship.

