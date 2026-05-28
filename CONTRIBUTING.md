# Contributing to Glucosphere

Thanks for your interest in contributing. This is an open demo + reference architecture for real-CGM forecast-monitoring on Databricks, and we welcome improvements from anyone — Databricks customers, partners, FE engineers, and external developers building on similar patterns.

## Getting started

1. **Read [`DEPLOY.md`](DEPLOY.md)** for the full deployment walkthrough — get a working deploy on your own Databricks workspace before proposing changes, so you can validate your contribution end-to-end.
2. **Local Python env via [`uv`](https://docs.astral.sh/uv/)** — `uv sync` once in the repo root creates the project venv (Python 3.11 per `.python-version`) used by `scripts/render_app_yaml.py` and `scripts/smoke_test.py`.
3. **Configure your workspace** — `cp .env.bundle.example .env.bundle` and fill in the three required tokens (catalog, schema, profile).

## Where to contribute

- **Open issues** — pick anything tagged `good-first-issue` or `help-wanted` if those labels are available
- **Pipeline + ML** — `Data_DataGen_ModelForecast/` (forecast models, incident simulation, DLT silver/gold, data generators)
- **App + UI** — `App/src/` (React frontend) and `App/databricks/app.py` (Flask backend / agent + Genie integration)
- **Bundle + deploy** — `databricks.yml`, `scripts/`, harness targets
- **Docs** — `README.md`, `DEPLOY.md`, `CHANGELOG.md`, per-folder `README*.md` files

## Branch + commit conventions

- **Branch naming**: `feature/<short-description>` or `fix/<short-description>` — kebab-case
- **Commits**: Conventional-Commits-ish — `feat(scope): ...`, `fix(scope): ...`, `docs: ...`, `chore: ...`, `refactor: ...`, `test: ...`. Subject lines ≤72 chars; body explains WHY when the change isn't self-evident.
- **Co-author trailer**: add `Co-authored-by: <Name> <email>` if pair-programmed or AI-assisted.

## Before opening a PR

- [ ] Code runs against the bundle's `cgm_pipeline_job` end-to-end (or a harness target if changes are isolated)
- [ ] **Smoke test passes 8/8**: `uv run python scripts/smoke_test.py --target <your-target> --profile <your-profile>`
- [ ] Visual sanity check on the App if you touched pipeline / data / App code:
  - Metrics Explained page renders the 4-panel comparison PNG
  - Device Support page heatmap shows expected firmware variety
- [ ] Comments / docs updated alongside code changes (avoid orphan stale doc references)
- [ ] No internal-history breadcrumbs in user-facing assets — workspace-specific paths, dated lapse notes, and internal run IDs belong in `CHANGELOG.md`, not in README/DEPLOY/inline comments

## PR description

Use this minimal shape (the existing PRs on this repo follow it):

```markdown
## Summary
- 1-3 bullets on what changed and why

## Test plan
- [ ] Bulleted checklist of how you validated the change
- [ ] Include smoke-test result + visual checks if applicable
```

## Review + merge

Maintainers (current: May Merkle-Tan, Justin Ward, Morgan Williams — see README Contributors section) will review and either merge or request changes. For non-trivial changes, expect at least one round of discussion on design — that's healthy, not a roadblock.

## Reporting bugs

Open a GitHub issue with:
1. What you expected
2. What actually happened
3. Steps to reproduce (target name, baseline mode, command sequence)
4. Smoke-test output if relevant

For sensitive issues (security, PHI handling concerns), email a maintainer directly rather than opening a public issue.

## License + acknowledgments

By contributing, you agree your contributions are licensed under the same terms as the rest of the repository. See `LICENSE` if present.

Real CGM data comes from the [HUPA-UCM dataset](https://data.mendeley.com/datasets/3hbcscwz44/1) (Universidad Complutense de Madrid) — please cite appropriately if you publish research derived from this repo.
