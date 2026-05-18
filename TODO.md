# TODO — Glucosphere dual-baseline work

## Remaining plan-commits (after C.1-C.6 closed 2026-05-16)

- [ ] **Commit D — distribution comparison across the 3 baseline modes (NEXT, ~30 min + test).**
  New notebook `Data_DataGen_ModelForecast/dual_02_compare_baseline_modes.py` (~150-250 LOC). Runs all three modes + emits a side-by-side comparison: row counts, patient counts, glucose stats (mean/median/std/percentiles), hypo/normal/hyper percentages, histograms, KS-test for distribution similarity. Demo value + regression catcher.

- [x] **Commit E — hygiene + valueFrom + smoke checklist (CLOSED 2026-05-18).** Three batched items:
  1. ~~`valueFrom` conversion in `app.yaml`~~ — **REVERTED 2026-05-18 (`8942f4d`)**. `valueFrom: <resource-name>` did not resolve at runtime because the app object's `resources` field came back empty after `bundle deploy` (verified via `/api/2.0/apps/glucosphere-dashboard`). ENDPOINT_NAME and GENIE_SPACE_ID came up empty → 500 errors from Clinical Analysis + Genie panels. Reverted to plain `value:` with hardcoded IDs; `render_app_yaml.py` updated to rewrite the env var value alongside the resource block. Resources block stays declared for SP permissions but no longer load-bearing for env-var resolution.
  2. Stale-doc cleanup — partially done in subsequent commits.
  3. App smoke-test checklist in DEPLOY.md — see DEPLOY.md Step 11 (added in commit `590b724`).

- [ ] **Commit F — restore Lakebase per v0.1 architecture (~half-day).**
  Lakebase = Databricks-managed Postgres (autoscale tier: scale-to-zero, branching, instant restore). v0.1 architecture diagram shows it between silver/gold Delta and the App layer; not currently implemented. Declare as DABs resource on `mmt_aws_usw2` + wire Flask to read/write certain state from Lakebase where OLTP latency matters. **Use case TBD at kickoff:** clinician interaction state / real-time alert cache / app OLTP / demo showcase. Effort: bundle resource config (~30 min) + Lakebase provisioning (~15 min) + Flask wiring (~1-2 hr) + tangible demo (~30 min).



> **End-of-session 2026-05-15 ~3:30am note:** Primary branch shifted from
> `feature/dual-baseline-hls-amer` → `feature/dual-baseline-mmt-aws-usw2`
> (decision made, not yet executed). Reason: fe-vm-hls-amer App cap blocks
> end-to-end validation; mmt-aws-usw2 is unblocked.
>
> **In-flight:** `Data_DataGen_ModelForecast/utils/schema_contract_preflight.py`
> is drafted but UNTRACKED on hls-amer branch. Survives checkout. Next session:
> switch to mmt-aws-usw2, wire `%run`, commit C.1.
>
> Working notes for this branch. The forward plan lives here so anyone picking up
> the work can `cat TODO.md` and see what's next. Remove or relocate before
> merging upstream to `feature/ward-app-cleanup-upstream`.
>
> Richer context lives in:
>
> - `ref_notes/2026-05-15_session-snapshot.md` — latest session per-commit summary + verified facts
> - `ref_notes/2026-05-14_*.md` — original plan + branch divergence analysis
> - Cross-session: `~/.claude/projects/-Users-may-merkletan-Documents-Projects-hls-medtech-buildathon-glucosphere/memory/`

## Commits done on this branch

- `3ad3d0a` — Add hls_amer DABs target + `scripts/render_app_yaml.py`
- `289cd76` — Flip default target → hls_amer; consolidate Ward's dev+prod → `ward_consolidated`
- `bec587b` — Add `baseline_source` bundle var + `condition_task` dispatch + stub `01_ingest_real_baseline.py`

## Pending commits (plan order)

- [ ] **Commit C** — replace stub `Data_DataGen_ModelForecast/01_ingest_real_baseline.py` with real implementation. Split into 4 sub-commits:
  - [ ] **C.1** — add shared `Data_DataGen_ModelForecast/utils/schema_contract_preflight.py`. Validates `diabetes_data` for required cols, 5-min cadence, ≥95% non-null glucose, ≥90% per-patient coverage. `%run` from `01_generate_synthetic_baseline.py` AND (later) `01_ingest_real_baseline.py`. Verify synthetic data passes before moving on. (~80 LOC)
  - [ ] **C.2** — implement `download` mode by porting from `origin/hls-buildathon-main`: `01_download_data.py` (134 LOC, HUPA-UCM Mendeley) + `02_parseNcombine_processed_data.py` (133 LOC, parse + merge → `diabetes_data`). Widgets: `SOURCE_MODE=download`, `DOWNLOAD_VOLUME`. (~150-200 LOC after consolidation)
  - [ ] **C.3** — implement `table` mode. Widgets: `SOURCE_MODE=table`, `SOURCE_CATALOG`, `SOURCE_SCHEMA`, `SOURCE_TABLE` (codex C1 — parameterize, don't hardcode). Fail-fast if not provided. (~30 LOC)
  - [ ] **C.4** (optional) — port subset of `03_extract_baselineTS_EDAcheck.py` (1,266 LOC, mostly EDA viz) to emit `baseline_timeseries` + `baseline_windows_metadata` QC tables. Recovers EDA value lost on cleanup; not downstream-required.
- [ ] **Commit D** — validation: row counts + glucose distribution across all 3 modes (synthetic / table / download); possibly also a `02_ai_data_validation.py`
- [x] **Commit E** — repo hygiene + ~~deferred `valueFrom` conversion~~ (reverted 2026-05-18, see above) + app smoke-test checklist + stale-doc cleanup (`App/README.md`, accidentally-committed `.vite/deps/*`, stale notebook widget defaults, stale markdown comment at `05_..py:1733`)
- [ ] **Commit F** — restore Lakebase per v0.1 architecture (`Data_DataGen_ModelForecast/assets/architecture_0.1.png`); autoscale tier; declared as bundle resource on `hls_amer`

## Gates (blocking forward progress)

- **fe-vm-hls-amer 100-app cap blocks the App resource only** — Job (`glucosphere-full-setup-hls_amer`, id `669309144598502`) + DLT pipeline (`glucosphere-cgm-silver-gold-hls_amer`, id `729fb0d4-0417-48a6-8c92-b8c63e31efaa`) already deployed. **Does NOT block Commits C / D.**
  - **Recommended:** workspace admin quota bump (durable fix; workspace is genuinely 95/100 ACTIVE)
  - Both ERROR apps systemically un-deletable from fe-vm-hls-amer alone — SPs registered in `fevm-industry-solns-buildathon` (`237438879023004`); owner SP cleanup there required first (`facers2` SP `75351379136763`, `biomcp-server` SP `73911714383112`). Admin permission on fe-vm-hls-amer does NOT bypass this.

## Follow-up deliverables (post dual-baseline closure)

- [ ] **One-command deploy template** for fresh-workspace bootstrap. User-facing config (`glucosphere.deploy.yaml`) with minimum input: workspace host/profile + UC catalog name. Script auto-derives warehouse ID, MAS/KA endpoint names, Genie space ID, app SP, etc. Replaces today's render-script + manual-orchestration ritual. Captured in memory `project_deploy_template_design.md`. ~1-2 days focused work. Slotted AFTER C/D/E/F.

## Follow-up features

- [ ] **Implement "Export to Chart"** on `DeviceSupportDashboard.jsx` (currently labeled "(placeholder)" + disabled). Origin: button was copied in from EMU scaffold in `d0bcf7c`, never wired up. **Faithful intent:** turn the Clinical Analysis text into a comparative-stats chart for this device vs fleet (hyperglycemia rate, hypoglycemia rate, mean glucose, std, reading/incident counts). **Recommended approach** (per 2026-05-16 discussion): new Flask endpoint `/api/device/stats?device_id=X` returns structured numbers from gold tables → new React chart component (likely hand-rolled SVG matching the `IncidentCharts.jsx` style; recharts isn't currently a dependency). Estimate ~1.5-2 hr. Could also extend KA/MAS to return structured comparison data alongside the text analysis.

## Post-validation cleanup (after L3 end-to-end test green-lights the foundation)

- [ ] Branch tidy-up — review `feature/dual-baseline-mmt-aws-usw2` + `feature/dual-baseline-hls-amer` commit history; consider squashing partial commits (e.g., `1581e9f` + `72664f9` were the same logical change split by a `git add` mishap)
- [ ] Notebook filename cleanup — revisit the `dual_` prefix once things stabilize; may simplify or rename for clarity
- [ ] Reconcile branch primacy — once fe-vm-hls-amer cap is unblocked, cherry-pick C.1+ work back to `feature/dual-baseline-hls-amer` and decide which branch is the merge-back target
- [ ] Reconsider catalog choice on mmt_aws_usw2 — may want `mmt_aws_usw2` (workspace-default) instead of `mmt_aws_usw2_catalog` so it can be shared/bound to other workspaces. Currently writes are in `mmt_aws_usw2_catalog.glucosphere_dev`; would mean re-running the setup job pointing at the other catalog (or migrating tables)

## Open decisions

- [ ] Should the real-baseline path emit `baseline_timeseries` + `baseline_windows_metadata` as QC tables (recovers some EDA value lost on cleanup)?
- [ ] Add `02_ai_data_validation.py` comparing real vs synthetic distributions — Commit D or its own commit?
- [ ] Lakebase use case for Commit F (clinician interaction state / real-time alert cache / demo) — defer to F kickoff
- [ ] Push the 3 local commits to origin — waiting for explicit "push" / "go ahead" / "ship it"

## Comms / unblock (async, optional)

- [ ] Send Slack to fe-vm-hls-amer channel about quota bump (drafts available — short + long versions)
- [ ] Optional DMs: jeff.shmain re `biomcp-server` SP cleanup; guanyu.chen re `facers2` (likely already knows it's stuck)

## Sibling branches

- **`feature/dual-baseline-mmt-aws-usw2`** — backup / portability-test branch (created from this branch). Adds `mmt_aws_usw2` target in `databricks.yml` pointing at fevm-mmt-aws-usw2 workspace (1/100 app cap, plenty of headroom). State: `databricks.yml` edit uncommitted on that branch, app.yaml was rendered locally. Resume the portability deploy test from there once Commit C has the real-data path working.
