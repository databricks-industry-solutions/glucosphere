# Changelog

> **Branch:** `feature/dual-baseline-mmt-aws-usw2`
> **Parent:** `origin/feature/ward-app-cleanup-upstream` (Justin Ward's post-buildathon cleanup branch)
> **Tracked range:** from `bd15400` (branch base, 2026-05-17) through current HEAD on origin. See dated sections below for per-commit detail.

All notable changes to the Glucosphere demo project on the
`feature/dual-baseline-mmt-aws-usw2` branch are documented in this file.

Format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Dates use ISO 8601 (YYYY-MM-DD), grouped by author date of the commits
landed on the branch.

This project is a Databricks demo, not a versioned library — entries are
grouped by date rather than semver tags. The "Unreleased" section above the
dated history captures work in progress / planned work.

---

## [Unreleased]

### Planned

- **#69 — Full repo branch cleanup audit** (new 2026-05-19) — holistic sweep:
  for each top-level file, assess (a) relevance to current branch state,
  (b) upstream dependencies, (c) downstream dependencies,
  (d) staleness markers (TODOs, dated references, removed-notebook mentions).
  Pairs with #46/#50/#53 docs work. Half-day to full-day effort.
- **#42 — Lakebase F kickoff** (alert state cache integration, ~4 hr) — alerts +
  alert_transitions tables on workspace-scoped Lakebase Autoscaling instance;
  Flask wiring; React Open Alerts panel as `#56` follow-up. Design landed
  earlier in week (see `ref_notes/2026-05-16_lakebase-f-kickoff-design.md`).
- **#39 — Standalone catalog cutover** (`mmt_aws_usw2_catalog` →
  `mmt_aws_usw2`) — manual playbook test; includes schema-naming decision
  (`glucosphere_dev` → `glucosphere`?). Validates cutover playbook for the
  eventual fe-vm-hls-amer rollout.
- **#43 — Deploy template** (`glucosphere.deploy.yaml` +
  `scripts/deploy_glucosphere.py`) — one-command fresh-workspace bootstrap.
  Captures patterns from #41/#42/#39.
- **#48 — Renumber + rename notebooks for clean execution-order convention**
  (POST #43) — pairs naturally with #43 deploy-template work. Re-apply the
  notebook-rename playbook captured at
  `ref_notes/2026-05-18_notebook-rename-playbook.md` (used 2026-05-18 for
  dual_* prefix on 04/05/06/10). Bigger pass: re-numbering execution-order
  prefixes across all notebooks for new-reader clarity.
- **fe-vm-hls-amer catalog rollout** — applies cutover playbook + deploy
  template once that workspace's 100/100 app quota is unblocked (admin SP
  cleanup of cross-workspace SP entanglement still pending in parent
  workspace).
- **#68 — Verify synthetic baseline path end-to-end** —
  `bundle deploy --var "baseline_source=synthetic"` against a sandbox schema
  (NOT live `glucosphere_dev`); confirm `condition_task` dispatch + spot-check
  incident plots + React charts; drop sandbox after. Synthetic path hasn't
  been re-validated since v9 palette + two-incident mirror landed (last
  validation 2026-05-15).
- **#64 — Markdown audit + cleanup sweep** across `dual_*` notebook
  `# MAGIC %md` cells (post-bidirectional + post-palette + post-rename).
  Targets the human-readable narrative inside notebooks for review quality.
- **#46 — Rewrite `Data_DataGen_ModelForecast/README.md`** to reflect
  cleanup-branch state + `dual_*` notebooks (current text references deleted
  `01_download_data.py` / `02_parseNcombine_processed_data.py` /
  `03_extract_baselineTS_EDAcheck.py`).
- **#47 — Extract shared incident-sim helper** (followup to #41 Option 3) —
  consolidate duplicated logic between `dual_05_*_Bidirectional.py` and
  `dual_05_*_SingleIncident.py` siblings.
- **#49 — Upgrade Figure 2 (MAE) / Figure 3 (Glucose Timeline) to 4-panel
  direction-breakout** — current 3-panel views (all / affected / unaffected)
  could split affected into +bias / −bias for direction-specific signal.
- **#50 — Add demo usage / deployment instructions for end users** — pairs
  with #46 README rewrite.
- **#53 — Incorporate Lakebase positioning into README + demo docs** —
  lands once #42 implementation is live so docs match what the app actually
  does. Pairs with #46/#50.
- **#58 — Send fe-vm Variant E follow-up** to unblock app quota +
  Lakebase enablement on fe-vm-hls-amer.
- **#40 — User review of README** (commit `d897eaa`).
- **Landing-page intro to demo's component map** — orientation banner on
  GlucoStream Intelligence landing page explaining the four sub-dashboards
  (GlucoStream, Device Support, Diabetes Coach, Care Management placeholder)
  and which persona each serves.
- **DAIS demo readiness** — polish for booth pickup if CGM /
  connected-device monitoring use cases come up.

### Open question

- **Workspace decision** (raised with Rebecca 2026-05-18): keep on
  fe-vm-hls-amer (currently 100/100 app quota blocked) OR move to newer prod
  workspace where Genesis Workbench is being added via
  databricks-industry-solutions accelerator repo.

---

## [2026-05-19]

Diabetes Coach rename, simulation framing on Metrics Explained, plot polish
v9 finalization, asset refresh, full push + deploy + run.

### Added

- `MetricsExplained.jsx`: "Why this monitoring stack matters" callout above
  the 3 incident charts — frames Abbott FreeStyle Libre FDA recall parallel
  (over-read + under-read), direction-agnostic MAE detection, and
  `incident_direction` drill-in (`bfdcc14`).
- `MetricsExplained.jsx`: page-intro simulation disclaimer paragraph and
  mid-page simulation reminders in "How MAE alerts are triggered" + "Device
  Calibration Bias" sections (`bfdcc14`).
- `MetricsExplained.jsx`: "How MAE alerts are triggered" section with
  embedded 4-panel distribution PNG (`5b09747`).
- Transparent-background PNG export pipeline in
  `dual_05_*_Bidirectional.py`: notebook `savefig(transparent=True)` →
  UC Volume `/Volumes/{catalog}/{schema}/landing_zone/dual_05_assets/` →
  `databricks fs cp` to `Data_DataGen_ModelForecast/assets/` (`a1757c4`).

### Changed

- Renamed Clinician Dashboard → Diabetes Coach Dashboard (full surface):
  React file `ClinicianDashboard.jsx` → `DiabetesCoachDashboard.jsx`, folder
  `ClinicianDashboard/` → `DiabetesCoachDashboard/`, default-export function
  name, route `/clinician` → `/diabetes-coach`, all display text +
  landing-page nav tile, DABs app description, DEPLOY.md MAS section,
  TODO.md Lakebase Commit F notes (`55d4bd1`). Persona subtitle "Provider
  Encounter Preparation" intentionally retained — workflow framing still
  relevant for the Diabetes Coach persona.
- Unified semantic palette across notebook + React app + assets:
  `darkgray` = true / baseline, `mediumturquoise` = observed / clean,
  `red` = positive-bias cohort, `blue` = negative-bias cohort,
  `lightcoral`/`lightblue` = hypo/hyper threshold zones (`197e40e` +
  `d1be32a` + `1ec5b59`).
- Refreshed `Data_DataGen_ModelForecast/assets/` PNGs to v9 unified-palette
  outputs (`44fa206`).
- `dual_05_*_Bidirectional.py` plots: shared y-axis across all 3 panels of
  Figure 2 (MAE) and Figure 3 (Glucose Timeline) — panel-to-panel amplitude
  visually comparable; arrow tips on yellow callout labels now hit the RED
  cohort peak / BLUE trough, not the green true-glucose line; 2-blank-line
  breathing space between Distribution Statistics table and the 4-panel
  figure (`d095c2a` + `197e40e`).

### Fixed

- `MetricsExplained.jsx:648` literal `>` characters in JSX text content
  escaped to `&gt;` (HIGH `>5%` etc.) — clears pre-existing
  `vite:esbuild` warning (`55d4bd1`).
- `dual_05_*_Bidirectional.py` Fig 1 ax2 NaN-direction labeling bug
  (positive cohort no longer mislabeled "negative" when opposite-cohort
  column is NaN) — `pd.notna()`-aware comparison replacing Python `or`
  truthiness (`d095c2a`).

### Documentation

- **Consolidated `AGENT_DEPLOY_INSTRUCTIONS.md` → `DEPLOY.md`** — deleted
  AGENT_DEPLOY_INSTRUCTIONS.md (344 lines, ward-demo workspace-specific,
  ~70% overlap with DEPLOY.md). Unique content folded into DEPLOY.md:
  agent-prompt callout at top, Verification Checklist section, Key File
  Locations tree, pre-flight catalog/schema/volume creation snippet.
  Updated DEPLOY.md: CLI version bumped to v0.281.0+, Architecture Overview
  rewritten with current `dual_*` notebook names + condition_task dispatch,
  Step 2 variables refreshed to actual `databricks.yml` defaults,
  target-specific section refactored to surface `mmt_aws_usw2` as the
  active demo target alongside `hls_amer` (historical/blocked), added the
  `--var baseline_source` placement gotcha section, expanded Troubleshooting
  with all the AGENT_DEPLOY entries. Historical AGENT_DEPLOY content
  preserved on `origin/feature/ward-app-cleanup-upstream` (commit `fc214eb`).
- **Generified `databricks.yml` top-level catalog default** — `default:
  hls_amer_catalog` → `default: glucosphere_catalog` (a generic placeholder
  name new deployments can create). Added explicit `catalog:
  hls_amer_catalog` override to the `hls_amer` target's `variables:` block,
  preserving existing `bundle deploy -t hls_amer` behavior exactly.
  Validated both `hls_amer` and `mmt_aws_usw2` targets parse cleanly via
  `bundle validate`. Also updated 5 notebook widget defaults to match the
  new generic placeholder: `dual_01_ingest_real_baseline.py`,
  `utils/dual_check_pre_baseline_grants.py`,
  `utils/dual_check_post_endpoint_grants.py`, `utils/dual_sanity_summary.py`,
  `utils/dual_validate_baseline_source.py` (these defaults only apply when
  notebooks are run interactively outside the bundle; bundle job runs always
  pass the catalog via `base_parameters`).
- **Removed dead Ward-branch targets from `databricks.yml`** — deleted the
  three commented-out historical targets (`ward_consolidated`, `azure`,
  `azure2`) that hardcoded Justin's workspace-specific host + catalog +
  warehouse IDs (not portable, never used by our active deploys). Replaced
  with a generic template-style commented block showing the YAML structure
  for adding new targets. Authoritative copies live on
  `origin/feature/ward-app-cleanup-upstream`. ⚠️ Side-effect to be addressed
  under #69: `deploy.py:199-269` has four hardcoded `ward_consolidated`
  references that are now orphaned (the script was Justin's pre-DABs
  deployment wrapper; our active deploys use `databricks bundle deploy` /
  `bundle run` directly, not `python deploy.py`).
- **Added "Agent-assisted deployment" section to `DEPLOY.md`** — placed
  between Verification Checklist and Key File Locations. Surfaces the
  skills to activate at session start, memory + ref_notes to pre-load,
  long-running job polling pattern, verification discipline, and common
  agent lapses to avoid (including the 2026-05-19 `baseline_source` default
  lapse).
- **Pre-existing markdownlint warnings** in `DEPLOY.md` (MD040 missing
  language on code fences, MD060 table column style, MD031 blanks-around-
  fences) are unrelated to this session's edits; flagged for the `#69`
  markdown sweep.
- **Pre-existing yaml-schema deprecation warnings** in `databricks.yml`
  (lines 95, 148, 404 — "field is deprecated" per the Declarative
  Automation Bundles schema) are unrelated to this session's edits;
  flagged for `#69` to investigate which DABs fields need migration.
  See task #69 (Full repo branch cleanup) for the broader sweep.
- **`dual_05_*_Bidirectional.py` Figure 4 — readability fix for dark-themed
  React app.** Wrapped the 4-panel distribution-comparison figure in an
  rcParams save/override/restore block that sets `text.color`,
  `axes.labelcolor`, `xtick.color`, `ytick.color`, `axes.edgecolor`, and
  `axes.titlecolor` to white for the duration of the figure construction
  + savefig. The resulting PNG (`fig4_distribution_comparison_4panel.png`,
  saved with `transparent=True`) renders subplot titles, axis labels, and
  tick text readably on the dark React app background instead of
  black-on-near-black (the prior PNG had dark titles invisible against
  the slate-950 React bg — flagged by user with screenshot 2026-05-19).
  Tuned for dark-theme-only (glucosphere-dashboard ships dark-only as of
  2026-05-19); if a light-theme toggle is added later, drop the override
  or use bbox-backed text. ⚠️ The **live app's embedded PNG won't refresh
  until the next pipeline run** regenerates the asset to UC Volume +
  copies it back to `Data_DataGen_ModelForecast/assets/`. Next
  `bundle run -t mmt_aws_usw2 glucosphere_full_setup` will trigger that.
- **`DEPLOY.md` Step 6 deploy command** — replaced workspace-specific
  example values (`catalog=hls_glucosphere`, `schema=cgm`) with generic
  placeholders (`<your-catalog>`, `<your-schema>`, `<your-profile>`) and
  added a note that for active targets users should `-t <target>` instead
  of `--var` overrides.

---

## [2026-05-18]

Two-window mirror simulation, dual_* notebook rename, KPI/Genie/MAS auth
fixes, plot polish iterations v1-v8.

### Added

- Two-incident mirror simulation design: Window 1 Day 2 +40 mg/dL on
  positive-bias cohort (Alpha/Gamma devices), Window 2 Day 5 -40 mg/dL on
  negative-bias cohort (Beta/Delta devices). Distinct x-position spike
  events across React dashboard charts and inference notebook plots
  (`6f7c91f`).
- Device-model-correlated cohort selection (`c029b38`).
- Per-incident yellow callout labels in `dual_05_*_Bidirectional.py` plots
  (`c029b38`).
- Absolute-glucose 3-line chart variant + smoother line style on React
  dashboard (`a0f7e13`).
- Genie query UX: `Loader2` spinner + "Sending query… typically 3-10
  seconds" status banner (`dfba524`).
- Genie persistent time-window interpretation instruction (interpret "last
  N hours/days" against `MAX(time)` not `NOW()`, since demo data is
  backdated to Jan 2026) (`dfba524`).

### Changed

- Renamed notebooks `04`/`05`/`06`/`10` → `dual_04`/`dual_05`/`dual_06`/
  `dual_10` to match the `01`/`09` `dual_*` convention. Pristine Ward-branch
  versions preserved under `previous/Data_DataGen_ModelForecast/`
  (gitignored). Single-incident variant of the inference notebook now sits
  alongside as `dual_05_*_SingleIncident.py`, sibling to the active
  `_Bidirectional` dispatched by the pipeline (`8366c90`).
- Cosmetic cleanup: `dual_05_*_Bidirectional.py` markdown cells,
  `MetricsExplained.jsx` docs, `TODO.md` `valueFrom` notes (`90519c1`).
- Removed downsampled markers from MAE + Bias Delta charts in React
  dashboard (`3ef123a`).

### Fixed

- `dual_05_*_Bidirectional.py` `NameError` on
  `unaffected_incident_mae_15m` / fleet incident MAE vars (default to
  `0.0` when no incident data present) (`020e079`).
- KPI tiles: `High-Risk Alerts` (last-24h → last-3h for usable
  signal-to-noise), `Device-OOR` time filter, MAS + Genie env-var resolution
  (`valueFrom` pattern wasn't resolving against the Apps platform; reverted
  to hardcoded value with `scripts/render_app_yaml.py` rewriting per target)
  (`8942f4d`).
- Incident shading on MAE + Bias charts now renders per-block instead of
  one big rect spanning the Day 2 → Day 5 gap (`e97a2a1`).
- MAE chart (fleet vs affected) + Glucose Timeline delta view rendering on
  React dashboard (`c1d941b`).

---

## [2026-05-17]

Branch bootstrap on origin: first push of
`feature/dual-baseline-mmt-aws-usw2`, bidirectional viz pass on React +
notebook, Lakebase scaffolding.

### Added

- Lakebase alerts schema initializer (`#42` step 2) (`bd15400`) — boundary
  commit of this changelog range; references this schema in subsequent
  Lakebase work.
- Bidirectional Glucose Timeline two-line viz on React dashboard +
  matching MetricsExplained text + footer fix (`120d7b8`).
- Bidirectional plots in `dual_05_*_Bidirectional.py` notebook + React chart
  y-axis headroom (`bdf40ae`).
- Claude Code plugin setup section in `README.md` for maintainers
  (`026bd88`).

### Changed

- React app: `catalog`/`schema` now read via `/api/config` (Flask endpoint)
  instead of Flask-side string substitution (`d540fbf`) — removes the
  monkey-patch and makes the React side responsible for its own config
  lookup.

### Fixed

- `dual_05_*_Bidirectional.py` `AMBIGUOUS_REFERENCE` on `incident_direction`
  column in inference join (`#41` followup) (`ae5e2c6`).
