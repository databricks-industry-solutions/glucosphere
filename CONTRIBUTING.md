# Contributing to Glucosphere

Thanks for your interest in contributing. This is an open demo + reference architecture for real-CGM forecast-monitoring on Databricks, and we welcome improvements from anyone — Databricks customers, partners, FE engineers, and external developers building on similar patterns.

## Contributor License Agreement (CLA)

By submitting a contribution to this repository, you certify that:

1. **You have the right to submit the contribution.**  
   You created the code/content yourself, or you have the right to submit it under the project's license.

2. **You grant us a license to use your contribution.**  
   You agree that your contribution will be licensed under the same terms as the rest of this project, and you grant the project maintainers the right to use, modify, and distribute your contribution as part of the project.

3. **You are not submitting confidential or proprietary information.**  
   Your contribution does not include anything you don't have permission to share publicly.

If you are contributing on behalf of an organization, you confirm that you have the authority to do so. You agree to confirm these terms in your pull request. Any request that does not explicitly accept the terms will be assumed to have accepted.

## Getting started

1. **Read [`DEPLOY.md`](DEPLOY.md)** for the full deployment walkthrough — get a working deploy on your own Databricks workspace before proposing changes, so you can validate your contribution end-to-end.
2. **Local Python env via [`uv`](https://docs.astral.sh/uv/)** — `uv sync` once in the repo root creates the project venv (Python 3.11 per `.python-version`) used by `scripts/render_app_yaml.py` and `scripts/smoke_test.py`.
3. **Configure your workspace** — `cp .env.bundle.example .env.bundle.<target>` (one file per deploy target, named for the `databricks.yml` target key, e.g. `.env.bundle.gsphere`) and fill in the three required tokens (catalog, schema, profile).

> **Internal Databricks contributors** (using a `fevm-*` workspace): see [`docs/internal-setup.md`](docs/internal-setup.md) for the catalog naming convention — the `*_catalog`-suffixed catalog is workspace-default ("dev"), and the standalone non-suffixed catalog is the portable "prod" / live-demo target. Don't mix them.

## Adapting for your own workspace

The committed `databricks.yml` has **no hardcoded workspace hosts** — workspace selection is profile-driven (`DATABRICKS_CONFIG_PROFILE` in the gitignored `.env.bundle.<target>`), so external deployers don't need to edit it or add a target stanza ([`databricks.yml.example`](databricks.yml.example) is a reference mirror of it). Copy [`.env.bundle.example`](.env.bundle.example) → `.env.bundle.<target>` (one per deploy target) and fill in your catalog / schema / `~/.databrickscfg` profile. See [`DEPLOY.md`](DEPLOY.md) for the full deploy sequence.

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

## Keeping dependency tables current

Per-area **`DEPENDENCIES.md`** files (`App/DEPENDENCIES.md`, `Data_DataGen_ModelForecast/DEPENDENCIES.md` — linked from each area's README and the repo-root README) carry the dependency + license inventory — one row per direct dependency with: name, where it's used, why, source URL, and license. When you add, remove, or upgrade a direct dependency (anything in `App/package.json`, `App/databricks/requirements.txt`, or a notebook-level `%pip install`), update the table in the same PR:

- **Verify the license** from an authoritative source: `node_modules/<pkg>/package.json` `license` field for frontend; PyPI `info.license` / `info.license_expression` or `dist-info/METADATA` `License:` for backend; the upstream repo's `LICENSE` / `pyproject.toml` for edge cases.
- **Keep the "Where used" specific** — file paths, not vague subsystems. Future grepability matters when assessing impact.
- **Drop rows for removed dependencies** — leftover rows for uninstalled packages are stale by definition.

If a dependency is platform-provided (e.g. Databricks Runtime ships pyspark, the App platform provides the Python interpreter) rather than declared in a manifest, surface that in prose near the table rather than padding the table with non-declared items.

## Updating the CHANGELOG

We follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format,
date-grouped instead of semver-tagged (this is a Databricks demo, not a
versioned library). Entries are ordered newest-first.

**In the same PR that lands the change**, add an entry under today's date:

- If today's `## [YYYY-MM-DD]` section already exists at the top of the
  dated history, add a bullet under the appropriate sub-heading
  (`### Added` / `### Changed` / `### Fixed` / `### Removed`).
- If not, insert a new `## [YYYY-MM-DD]` section at the **top** of the
  dated history (just below the intro paragraph + provenance note, above
  the previous newest entry), with the relevant sub-headings.

What a good bullet captures:

- **WHAT** changed (concise — the diff explains the how)
- **WHY** it changed (the motivation, especially for behavior changes)
- File paths or resource names if they aid grep-ability later

What to keep OUT of CHANGELOG entries (this file is user-facing):

- Internal task numbers, run IDs, workspace-specific paths
- Iteration journey ("tried X, then Y, settled on Z") — only the final
  state matters
- Dated lapse notes or `TODO:` cleanup pointers

If you're unsure whether something warrants a CHANGELOG entry, ask in
the PR — small/internal changes (e.g., dependency bumps, comment-only
fixes) often don't.

## Before opening a PR

- [ ] Code runs against the bundle's `glucosphere_full_setup` job end-to-end (or a harness target if changes are isolated)
- [ ] **Smoke test passes** (8/8; 9/9 on Lakebase-enabled targets): `uv run python scripts/smoke_test.py --target <your-target> --profile <your-profile>`
- [ ] Visual sanity check on the App if you touched pipeline / data / App code:
  - Metrics Explained page renders the 4-panel comparison PNG
  - Device Support page heatmap shows expected firmware variety
- [ ] Comments / docs updated alongside code changes (avoid orphan stale doc references)
- [ ] No internal-history breadcrumbs in user-facing assets — workspace-specific paths, dated lapse notes, and internal run IDs belong in `CHANGELOG.md`, not in README/DEPLOY/inline comments
- [ ] No workspace-specific coords (catalog / schema / profile / app name / warehouse id) in committed `databricks.yml` stanzas **or their comments** — those live only in the gitignored `.env.bundle.<target>`; committed config carries generic placeholders (see `AGENTS.md` §6)

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

By contributing, you agree your contributions are licensed under the same terms as the rest of the repository — see [`LICENSE.md`](LICENSE.md) (Databricks DB License) and [`NOTICE.md`](NOTICE.md). For security issues see [`SECURITY.md`](SECURITY.md).

Real CGM data comes from the [HUPA-UCM dataset](https://data.mendeley.com/datasets/3hbcscwz44/1) (Universidad Complutense de Madrid) — please cite appropriately if you publish research derived from this repo.
