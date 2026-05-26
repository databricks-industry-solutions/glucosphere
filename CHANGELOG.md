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

#### Demo features (sequenced)

- **#42 — Lakebase F kickoff** (~4 hr) — alerts + alert_transitions tables on workspace-scoped Lakebase Autoscaling instance; Flask wiring; React Open Alerts panel as `#56` follow-up. Design landed earlier in week (`ref_notes/2026-05-16_lakebase-f-kickoff-design.md`).
- **#68 — Verify synthetic baseline path end-to-end** — `bundle deploy --var "baseline_source=synthetic"` against a sandbox; confirm `condition_task` dispatch + spot-check incident plots + React charts; drop sandbox after. Synthetic path not re-validated since v9 palette + two-incident mirror landed 2026-05-18.
- **#47 — Extract shared incident-sim helper** — consolidate duplicated logic between `dual_05_*_Bidirectional.py` and `dual_05_*_SingleIncident.py` siblings.
- **#70 — Post-pipeline asset refresh** (in flight 2026-05-19 evening) — `fs cp` fig4 PNG from UC Volume → repo, `npm run build`, commit + push, `bundle deploy + bundle run glucosphere_dashboard`. Pairs with the matplotlib fix in `6fd9222`.

#### Infra & portability

- **#39 — Standalone catalog cutover** (`mmt_aws_usw2_catalog` → `mmt_aws_usw2`) — manual playbook test; includes schema-naming decision (`glucosphere_dev` → `glucosphere`?). Validates the cutover playbook for the eventual fe-vm-hls-amer rollout.
- **#58 — Send fe-vm Variant E follow-up** — unblock app quota + Lakebase enablement on fe-vm-hls-amer.
- **fe-vm-hls-amer catalog rollout** — applies cutover playbook + deploy template once #58 unblocks the workspace's 100/100 app quota (admin SP cleanup of cross-workspace SP entanglement pending in parent workspace).

#### Deploy template & repo cleanup

- **#43 — Deploy template** (`glucosphere.deploy.yaml` + `scripts/deploy_glucosphere.py`) — one-command fresh-workspace bootstrap. Captures patterns from #41/#42/#39.
- **#48 — Renumber + rename notebooks** for clean execution-order convention (POST #43). Re-apply the notebook-rename playbook (`ref_notes/2026-05-18_notebook-rename-playbook.md`).
- **#69 — Full repo branch cleanup audit** (new 2026-05-19) — holistic sweep: for each top-level file, assess relevance + upstream/downstream dependencies + staleness markers. Pairs with the docs work below. Half-day to full-day effort.

#### Docs

- **#46 — Rewrite `Data_DataGen_ModelForecast/README.md`** — current text references deleted `01_download_data.py` / `02_parseNcombine_processed_data.py` / `03_extract_baselineTS_EDAcheck.py`; needs refresh to current `dual_*` notebook set.
- **#50 — Add demo usage / deployment instructions for end users** — pairs with #46.
- **#53 — Incorporate Lakebase positioning into README + demo docs** — lands once #42 implementation is live so docs match what the app actually does. Pairs with #46/#50.
- **#64 — Markdown audit + cleanup sweep** across `dual_*` notebook `# MAGIC %md` cells (post-bidirectional + post-palette + post-rename). Targets human-readable narrative inside notebooks for review quality.
- **#40 — User review of README** (commit `d897eaa`).
- **Landing-page intro to demo's component map** — orientation banner on GlucoStream Intelligence landing page explaining the four sub-dashboards (GlucoStream, Device Support, Diabetes Coach, Care Management placeholder) and which persona each serves.

#### Outreach

- **DAIS demo readiness** — polish for booth pickup if CGM / connected-device monitoring use cases come up.

### Open question

- **Workspace decision** (raised with Rebecca 2026-05-18): keep on
  fe-vm-hls-amer (currently 100/100 app quota blocked) OR move to newer prod
  workspace where Genesis Workbench is being added via
  databricks-industry-solutions accelerator repo.

---

## [2026-05-26]

Phase 1 (#68 synth + from_table E2E validation) preflight: React static rebuild reconciliation, mode-name rename (`real_from_{source,table}` → `from_{source,table}`), permanent sandbox harness targets via `mode: development`. Historical entries below retain the old names for accuracy of past-state record.

### Changed

- **Renamed baseline_source modes**: `real_from_source` → `from_source` AND `real_from_table` → `from_table`. Old names implied data origin (real); new names describe mechanism (download from external source URL vs CTAS from existing UC table). Source-agnostic: `from_table` can read from a synthetic-populated table or a real-populated one. Rename touched `databricks.yml`, `dual_01_ingest_real_baseline.py`, `dual_validate_baseline_source.py`, `dual_02_compare_baseline_modes.py` (incl. widget rename `REAL_FROM_*_SCHEMA` → `FROM_*_SCHEMA`), `App/databricks/app.py`, `App/src/pages/MetricsExplained.jsx`, `README.md`, `DEPLOY.md`.

### Added (in flight)

- React static rebuild reconciliation commit (`d260338`) — vite output for `b88d193` source state. Was deployed live 2026-05-19 evening but never committed; this commit brings repo HEAD into sync with the deployed bundle.
- Two permanent `mode: development` harness targets in `databricks.yml`:
  - `mmt_aws_usw2_synth_e2e` — `baseline_source=synthetic`, isolated sandbox schema `glucosphere_synth_e2e`. App: `glucosphere-synth-e2e`. DB: `glucosphere-oltp-synth-e2e`.
  - `mmt_aws_usw2_from_table_e2e` — `baseline_source=from_table`, **self-bootstrapping**: sources from `glucosphere_synth_e2e.diabetes_data` (synth harness output, NOT live `glucosphere_dev`). App: `glucosphere-table-e2e`. DB: `glucosphere-oltp-table-e2e`. Implication: synth_e2e MUST be run BEFORE from_table_e2e.

  Auto-prefixed `[dev may_merkletan]` on jobs + pipelines (see "Settled" below for auto-prefix caveats), paused schedules per DABs development-mode semantics (verified against `docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes`). Reusable for future regression validation against synth + from_table paths without touching the live `mmt_aws_usw2` target.

- `docs/2026-05-26_synth_e2e_findings.md` (`09d2239`) — team-shareable engineering write-up of the two latent bugs surfaced by the synth_e2e harness validation (see "Fixed" below). Self-contained with context, root cause analysis, fixes, retry commands, and an open question on stratified-sampler adaptivity for team review.

### Fixed

- **Bug 1 — `SCHEMA_NOT_FOUND` in `validate_baseline_source`** (`398d637`). The validate task is the FIRST task in `glucosphere_full_setup` and tried to `CREATE TABLE IF NOT EXISTS baseline_provenance` — but the schema didn't exist yet on fresh-schema deploys (dual_01's `CREATE SCHEMA` runs AFTER dispatch, which is AFTER validate). Latent because live `mmt_aws_usw2.glucosphere_dev` has existed since 2026-05-15. Fix: idempotent `CREATE SCHEMA IF NOT EXISTS` before the table write in `dual_validate_baseline_source.py:107`. Verified via run `891637990308752` validate task: SUCCESS.
- **Bug 2 — Stratified-sampler plan-size assertion fails on synthetic distribution** (initial fix `21baa5e` + tune `df0dc7c`). `dual_04_*.py:109` asserts `actual_plan_size == NUM_PSEUDO` (1000). The original 6 synthetic phenotypes (all means 95-175 mg/dL) produced 0 patients in `hypo_prone` (>15% readings <70) and `mixed` (residual) strata — sampler missing 64 + 1 = 65 patients. Latent because live `from_source` (real HUPA-UCM, 6.59% hypo + diverse profiles) populates all 4 strata naturally. Fix: added 2 phenotypes to `dual_01_generate_synthetic_baseline.py:52-69` — hypo-prone (mean 75, std 20) + brittle T1D. First brittle attempt (mean 135, std 55) closed the gap to 1 missing (got 999/1000) — landed in `normal_stable` @ ≈66% time-in-normal, above the 60% threshold. Tuned to (mean 150, std 70) so brittle lands in `mixed` (≈54% normal / ≈13% hypo / ≈33% hyper, none dominant).

### Settled

- **DABs resource naming pattern documented**: `[dev USERNAME]` auto-prefix encodes deployment-type + user (`workspace.current_user.short_name`); target-name suffix (`_synth_e2e`, `_from_table_e2e`) encodes baseline mode. No custom prefix needed for #68 — full reference saved as memory `reference_dabs_resource_naming_pattern.md`. Configurable prefix design (with `BUNDLE_VAR_dev_prefix` env-var override + `bundle-vars.env.example` template) deferred to task #74.
- **Auto-prefix scope (verified empirically 2026-05-26 via failed first deploy)**: `mode: development` auto-prefixes `jobs:` and `pipelines:` only — NOT `apps:` or `database_instances:` (those resource types have DNS-compliance constraints that exclude brackets). For non-prefixed types, target-level `resources:` overrides are needed to avoid name collisions with the live target.
- **Short_name normalization**: docs say prefix is `[dev ${workspace.current_user.short_name}]`. Empirical reality: dots in `short_name` get normalized to underscores. May's short_name = `may.merkletan` but actual prefix = `[dev may_merkletan]`.
- **App name 30-char limit (verified empirically)**: harness App names trimmed to fit (`glucosphere-synth-e2e` = 21 chars, `glucosphere-table-e2e` = 21 chars). The full `glucosphere-dashboard-synth-e2e` would have been 31 chars — over limit.
- **`real_from_table` E2E test never ran**: confirmed via git log + memory + ref_notes search — commit `1db686e` implemented the mode but no run-completion or memory entry records an actual end-to-end validation. Closed as part of #68 via the `mmt_aws_usw2_from_table_e2e` harness.

### Deferred (new tasks filed)

- **#72** — Smart-fallback in `dual_01_ingest_real_baseline.py`: if `${catalog}.${schema}.diabetes_data` already exists, auto-use `from_table` mode (skip Mendeley re-download). Operator-overridable via explicit `baseline_source=from_source`. ~30-50 LOC + tests. Slotted in Phase 7.
- **#74** — Per-deployer config pattern: introduce `bundle-vars.env.example` (gitignored personal `.env` per existing `App/.env.example` convention), document `BUNDLE_VAR_<name>` env-var override pattern, add configurable `dev_prefix` variable + smoke-test whether `presets.name_prefix` replaces vs stacks with auto `[dev USERNAME]`. Slotted in Phase 5 alongside #43 deploy template.
- **#50 (refined framing)** — Add a user-facing deploy walkthrough guide (`DEMO.md` or `GETTING_STARTED.md`) covering "you have a workspace + this repo; here's how to deploy step-by-step." Complements `DEPLOY.md` (technical reference) and #43 (one-command script). Phase 2.A cleanup item.

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
  React app** (iterated 4x on 2026-05-19 evening, current state below):
  - **rcParams override (narrowed)**: wrapped the 4-panel
    distribution-comparison figure in an rcParams save/override/restore
    block that sets `axes.labelcolor`, `xtick.color`, `ytick.color`,
    `axes.edgecolor`, and `axes.titlecolor` to white for the duration of
    the figure construction + savefig. **Critically does NOT override
    `text.color`** — that would make ALL text (including legend labels +
    `ax.text()` percentage annotations on bars) white, which fails on
    legend boxes (default white bg → invisible) and bar value labels (on
    colored bars where black is correct). Only OUTSIDE-the-axes text
    (titles / axis labels / ticks / edges) gets white; INSIDE-axes text
    stays default-black via unchanged `text.color`.
  - **Dark-themed legend boxes** (Option 3, superseded by Option 4 below):
    all 4 fig4 legend calls were briefly styled with
    `facecolor='#0a0e1a', edgecolor='gray', framealpha=0.85, labelcolor='white'`
    — slate-dark box w/ white labels. Visually integrated with the React
    app but read as "jarring" inside the notebook UI (light bg). Replaced
    by Option 4.
  - **Combined legend in CDF lower-right quadrant** (Option 4, current):
    per-axis `ax1`/`ax2`/`ax4` legends removed entirely; one combined
    legend lives on `ax3` (the CDF subplot), placed `loc='lower right'`
    in the empty quadrant that CDFs leave open (curves saturate to y=1
    by ~250-300 mg/dL, leaving the high-x/low-y region free). The combined
    legend is built by collecting `get_legend_handles_labels()` from `ax1`
    (4 cohort entries with descriptive `+40`/`-40` labels) and `ax4` (2
    threshold-line entries — Hypo `<70` / Hyper `>180`), deduped by
    label string. Six entries total; `labelcolor='#888888',
    facecolor='none', edgecolor='lightgray'` with a light dotted
    border (`linestyle=':', linewidth=1.2` applied via
    `legend.get_frame()`). No fill at all — the legend floats over
    whatever bg is behind it. Mid-grey `#888888` text + global
    `font.weight='bold'` rcParams override: ~5.7:1 contrast on dark React
    bg (passes WCAG AA small text) and ~3.55:1 on notebook UI light bg
    (passes WCAG AA large text, which the fontsize=12+bold combination
    qualifies for). Bold lifts perceived contrast on both bgs — user
    noted the subplot titles (already bold) were the "readable reference"
    the rest of the figure should match. Iteration history that landed
    here: framealpha=0.7 (darkgray Baseline swatch blended in),
    framealpha=0.95 (too cut-out), facecolor='lightgray'+0.85 (still
    a solid-feeling box), no-fill+dotted+#737373-text (axis labels still
    too dim on dark), then current #888888+bold+fontsize-12 — settled
    after user note "subplot title color worked so using that should
    be better". Cuts visual clutter (was 4 boxes → 1) and gives each
    subplot more breathing room for the data.
  - **Boxplot line components explicitly styled** (whiskers, caps,
    fliers): default-black on transparent bg was invisible on dark
    React (~1.5:1 contrast). Now `whiskerprops` + `capprops` + `flierprops`
    all set to `#888888`; `medianprops` kept `orange` for emphasis
    visible on both bgs.
  - **Bar value labels** (the `22%`/`6%`/`72%`/etc. annotations above
    each bar in the Distribution by Glucose Range subplot): bumped
    `fontsize=7` → `fontsize=9` so they're legible at the rendered PNG
    scale on both bgs.
  - **ax4 ordering bug fix** (discovered late-evening 2026-05-19): the
    Option 4 combined-legend builder must run AFTER `ax4 = axes[1, 1]`
    is created in the `Plot 4: Box plots` block; an earlier placement
    of the builder at the end of `ax3`'s setup raised
    `NameError: name 'ax4' is not defined` and failed run `897117790864535`.
    Builder now lives just before `plt.tight_layout()` so both `ax1`
    handles + `ax4` axhline-label handles are fully populated. Fix
    validated by run `1083492488019438` (SUCCESS, ~4 min).
  - **Single-task rerun pattern discovered**:
    `databricks jobs run-now --json '{"job_id":<JOB_ID>,"only":["incident_inference"]}'`
    runs JUST `incident_inference` (~5-10 min) instead of the full
    `glucosphere_full_setup` job (~45-60 min). Other tasks come back
    SKIPPED with `DISABLED`. Used today for fast PNG-regeneration
    iteration — runs `233809323742076` (narrowed rcParams), `249016198346734`
    (dark legend, now superseded), `921289767879821` (combined-legend
    intent ran on stale v3 workspace code — no-op), `897117790864535`
    (v4 with ax4 NameError, FAILED), and `1083492488019438`
    (v4 ordering fix, SUCCESS in ~4 min).
- **`App/databricks/app.py` — new `/uc-assets/<path>` Flask route**
  reading PNGs directly from UC Volume at runtime (via
  `GET /api/2.0/fs/files/Volumes/...`). Eliminates the `fs cp` step
  from the iteration cycle: pipeline writes PNG → UC Volume; App
  fetches PNG via UC Volume; no local copy + no vite re-import + no
  npm rebuild needed for PNG refresh. Matches the longevity solution
  agreed in earlier sessions but only landed in code today.
- **`App/src/pages/MetricsExplained.jsx` — switched to UC-Volume URL**:
  removed `import fig4DistributionPng from '../assets/...'` (vite static
  import) and replaced with `const FIG4_UC_PATH = '/uc-assets/dual_05_assets/fig4_distribution_comparison_4panel.png';`
  pointed at the new Flask route. `<img src={FIG4_UC_PATH}>` now fetches
  the latest UC Volume PNG on every page load.
- **`App/src/assets/fig4_distribution_comparison_4panel.png` — DELETED**
  (`git rm`) since vite no longer bundles it. Future plot PNGs follow
  the same pattern: write to UC Volume from notebook, never commit to
  `App/src/assets/`.
- **`dual_10_Grant_App_Permissions.py` — added `GRANT READ VOLUME ON
  VOLUME {CATALOG}.{SCHEMA}.landing_zone TO <app-sp>`** to the SQL
  grants list. Required for the new `/uc-assets/` route to read PNGs
  on fresh deploys. Live-applied on `mmt_aws_usw2` via direct SQL
  statement `01f153c4-edcf-1aa9-88aa-ad9e5d0d08ed` so the running
  App stops 403-ing; the notebook addition self-heals future workspaces.
  Result PNG (`fig4_distribution_comparison_4panel.png`, transparent bg)
  renders with `#888888` mid-grey titles / axis labels / tick text / axes
  edges (single rcParams override block covers all four). Combined legend
  in `ax3`'s lower-right empty quadrant: no fill (`facecolor='none'`),
  light dotted border (`linestyle=':', linewidth=1.2`), mid-grey labels.
  Default-black bar value labels stay default-black (intentional — they
  sit on top of colored bars). Legend patch handles get a thin
  mid-grey outline so the `darkgray` Baseline (Real) swatch is visible
  on dark bgs (darkgray-on-slate-950 was effectively invisible without
  the outline). Result: single PNG renders readably in BOTH the dark
  React app theme AND the notebook UI's light bg without per-theme
  regeneration.
- **`DEPLOY.md` Step 6 deploy command** — replaced workspace-specific
  example values (`catalog=hls_glucosphere`, `schema=cgm`) with generic
  placeholders (`<your-catalog>`, `<your-schema>`, `<your-profile>`) and
  added a note that for active targets users should `-t <target>` instead
  of `--var` overrides.
- **`MetricsExplained.jsx` content-accuracy pass + dynamic baseline_source**
  (evening 2026-05-19):
  - **High Risk Alerts time-window**: doc said "last 24 hours" but the
    actual `getHighRiskAlerts()` query (`GlucoseLanding/queries.js:162`)
    uses `INTERVAL 3 HOUR`. Updated doc to 3-hour with the rationale
    (incident-window length matching; 24h gets dominated by ~943 natural
    diabetic OOR baseline, 3h gives 495 baseline → 800 incident signal).
  - **Out-of-Range Device Readings query** (Device Support Dashboard) doc
    was missing the `INTERVAL 3 HOUR` time filter that the actual
    `getOutOfRangeDevices()` query (`databricksSQL.js:174`) has. Added
    the filter to the documented SQL + explained the 3-hour parallel
    with High Risk Alerts.
  - **FDA recall citations**: the "Why this monitoring stack matters"
    callout used to claim "Abbott FreeStyle Libre has FDA recalls on
    record for both over-reading and under-reading sensors" without
    citation. Added superscript footnotes [1] [2] linking to the
    actual FDA recall pages (FreeStyle Libre 3 Class I, ≈3M sensors,
    ≥860 serious injuries and 7 deaths linked to the under-read
    failure mode) + a Sources line below the recall claim. Verified
    URLs current as of 2026-05-19.
  - **Chart-location disambiguation**: prose used to say "three charts
    below walk through that detection chain" but the actual rendered
    charts live on the GlucoStream Intelligence landing page (chart 2
    is the only one embedded in Metrics Explained as a snapshot PNG).
    Rewrote per-chart location notes: chart 1 / chart 3 = "Lives on
    the GlucoStream Intelligence landing page"; chart 2 = "Snapshot
    PNG from the most recent incident-simulation pipeline run (dual_05
    notebook), embedded only in this Metrics Explained tab". Also
    rewrote the "top chart" / "bottom chart" inline references (3 sites)
    to fully-qualify the landing-page location.
  - **"page intro" wording**: replaced 2 occurrences with explicit
    "_About This Page_ above" pointers so a reader landing mid-page
    knows exactly where the provenance disclaimer lives.
  - **Broken job/run URL**: a stale "run 899387466814174" link pointing
    at job_id `464619060436574` (neither matches the real job 911600926545
    nor any actual session run) was replaced with a durable reference to
    the job page itself + a note that the App reads PNGs live from UC
    Volume via `/uc-assets/` so the snapshot refreshes on each pipeline
    run.
  - **Dynamic `baseline_source` (truly runtime, NOT deploy-time)**:
    deploy-time env vars can skew from actual pipeline-run mode. Solved
    with a provenance-table pattern (saved as memory `reference_provenance_table_pattern.md`):
    `dual_validate_baseline_source.py` `INSERT OVERWRITE`s a 1-row
    `{catalog}.{schema}.baseline_provenance` table at the head of every
    pipeline run; `App/databricks/app.py` adds `_get_baseline_provenance()`
    that queries this row via DBSQL with a 60s TTL cache + graceful
    fallback to `'real_from_source'` if the table doesn't yet exist
    (first-deploy edge case); `/api/config` exposes `baseline_source` +
    `baseline_source_detail` fields; `MetricsExplained.jsx` adds
    `useState` + `useEffect` to consume them and renders 3-mode
    conditional prose (`synthetic` / `real_from_source` / `real_from_table`).
    Result: the "About This Page" disclaimer about CGM signal provenance
    is always truthful for whatever the pipeline actually last ran.
    Validated 2026-05-19 evening via `jobs run-now --only validate_baseline_source`
    run `689520984699374` SUCCESS — provenance table populated, app
    `/api/config` returns live mode.

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

Branch bootstrap on origin: first push of `feature/dual-baseline-mmt-aws-usw2`, bidirectional viz pass on React + notebook, Lakebase scaffolding.

### Added

- Lakebase alerts schema initializer (#42 step 2) (`bd15400`) — first commit of the bundled push range `bd15400..bfdcc14` to origin; subsequent Lakebase work references this schema.
- Bidirectional Glucose Timeline two-line viz on React dashboard + matching MetricsExplained text + footer fix (`120d7b8`).
- Bidirectional plots in `dual_05_*_Bidirectional.py` notebook + React chart y-axis headroom (`bdf40ae`).
- Claude Code plugin setup section in `README.md` for maintainers (`026bd88`).

### Changed

- React app: `catalog`/`schema` now read via `/api/config` (Flask endpoint) instead of Flask-side string substitution (`d540fbf`) — removes the monkey-patch and makes the React side responsible for its own config lookup.

### Fixed

- `dual_05_*_Bidirectional.py` `AMBIGUOUS_REFERENCE` on `incident_direction` column in inference join (#41 followup) (`ae5e2c6`).

---

## [2026-05-16]

Dual-baseline path validated end-to-end on `fevm-mmt-aws-usw2`. Synthetic = 0.14% hypo / std 34; real_from_source = 6.6% hypo / std 57 / max 444 mg/dL. Lakebase Commit F kickoff design drafted (alert state cache + 2 tables + ~50 LOC SQL + ~4 hr effort) — implementation deferred as task #42.

### Changed

- `baseline_source` default flipped `synthetic` → `real_from_source` (commit `d897eaa`) + README rewrites: data fidelity section, getting-started, repo-structure refresh.
- Off-by-one sampling fix in `04_*.py` stratified sampler (commit `4abcb9b`) — deterministic cycling + `plan.count() == NUM_PSEUDO` assertion took the gold patient count from 999 → 1000.

### Added

- Persistent `glucosphere_distribution_comparison` job + inline `display(fig)` + UC Volume auto-provision (commit `88b140f`).
- Plot cell added to `dual_02_compare_baseline_modes.py` (commit `a742e10`).

Comparison numbers + plot interpretations in `ref_notes/2026-05-16_dual-baseline-comparison-plots.md`. C/D/E plan sub-commits all validated against `mmt_aws_usw2_catalog.glucosphere_dev_test*` sandbox schemas (since dropped).

---

## [2026-05-15]

Plan execution start: `feature/dual-baseline-mmt-aws-usw2` branched off `origin/feature/ward-app-cleanup-upstream` after fe-vm-hls-amer hit 100/100 app quota (cross-workspace SP entanglement blocking admin deletion).

### Added

- `hls_amer` DABs target + `scripts/render_app_yaml.py` (rewrites the 7 per-target fields in `App/databricks/app.yaml`) + `.gitignore ref_notes/` (commit `3ad3d0a`).
- Top-level bundle var defaults flipped to hls_amer values (commit `289cd76`) — default target → hls_amer; consolidated Ward's dev+prod into `ward_consolidated` (now removed 2026-05-19).
- `baseline_source` bundle var + `condition_task` dispatch + stub `dual_01_ingest_real_baseline.py` (commit `bec587b`).

### Fixed

- Notebook 09 silent MAS-creation failure (commits `f509dfd` + `b3d3ed0`): KA-ready wait up to 10 min requiring `status==ONLINE`; endpoint-name JSON path fix at `.tile.serving_endpoint_name` not `.status.*`.

### Settled

- (C4) `${var.*}` does NOT interpolate inside `App/databricks/app.yaml` — `scripts/render_app_yaml.py` is the canonical mechanism per Databricks Apps env-vars docs.
- (C5) May has catalog visibility on both `hls_glucosphere` and `hls_amer_catalog` on fe-vm-hls-amer.

L3 end-to-end VALIDATED on `fevm-mmt-aws-usw2`: full Glucosphere stack (synthetic baseline → diabetes_data check → modeling → DLT silver/gold → MAS/KA/Genie → app live). Detail in `ref_notes/2026-05-15_session-snapshot.md`.

---

## [2026-05-14]

Pre-work discovery: branch divergence analysis between `origin/hls-buildathon-main` (real HUPA-UCM ingest, 25 T1D patients) and `origin/feature/ward-app-cleanup-upstream` (Justin Ward's cleanup: Asset Bundle deploy + synthetic-only baseline, real-data ingest deleted).

### Findings

- Real-data nuance lost on cleanup — HUPA-UCM 25-patient priors + 1,266-LOC `03_extract_baselineTS_EDAcheck.py` replaced by textbook phenotypes + AR(1) dynamics in new `01_generate_synthetic_baseline.py` (recoverable from git history; `04/05/06` modeling spine intact).
- Cleanup branch ships Asset Bundle targeting 4 workspaces with `App/databricks/app.yaml` hardcoding `azure`-target IDs that `deploy.py` patches at deploy time.
- Lakebase IS in the v0.1 architecture (`Data_DataGen_ModelForecast/assets/architecture_0.1.png`) — Postgres component between silver/gold Delta and the App layer, not yet implemented on either branch; added as Plan Commit F.

Codex 1st-pass + 2nd-pass cross-checks folded in. Snapshot persisted to `ref_notes/2026-05-14_branch-divergence-snapshot.md` + dual-baseline plan drafted (originally 3 modes: `synthetic` / `real_from_table` / `real_from_source` — later collapsed to 2 at DABs level via `condition_task` on 2026-05-15).
