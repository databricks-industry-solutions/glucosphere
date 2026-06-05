# Changelog

> **Provenance.** The dated entries below capture the dual-baseline series
> of changes brought into `main` via the initial PR from
> `feature/dual-baseline-mmt-aws-usw2`, which forked from the post-Buildathon
> cleanup base `feature/ward-app-cleanup-upstream` at commit `bd15400`
> (2026-05-17). See per-date sections for commit-level detail. New entries
> are appended at the **top** of the dated history (newest-first).

All notable changes to the Glucosphere demo project are documented in
this file.

Format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Dates use ISO 8601 (YYYY-MM-DD), grouped by author date of the commits
landed in the project.

This project is a Databricks demo, not a versioned library — entries are
grouped by date rather than semver tags.

---

## [2026-06-05]

Teardown tooling to complement the per-target deploy convention.

### Added — `scripts/teardown_target.py` + DEPLOY.md teardown section
- **`scripts/teardown_target.py`** — deletes the workspace-global resources that `databricks bundle destroy` leaves behind: Agent-Bricks **KA + MAS tiles** (`/api/2.0/tiles/{id}`) and their serving endpoints, the **`Glucosphere_Forecast_{15,30}min`** forecast endpoints, and the **Genie space** (`/api/2.0/data-rooms/{id}`). Matches by `--suffix` (harness/sandbox) or `--names` (exact, for the live empty-suffix deploy — suffix-matching is unsafe with `""`). **Dry-run by default**; `--apply` to delete. Each resource is GET-verified before deletion.
- **`DEPLOY.md` "Teardown"** rewritten to the 3-part reality: (1) `teardown_target.py` for the non-bundle-managed agents/endpoints/Genie, (2) `bundle destroy -t <target>`, (3) `DROP SCHEMA … CASCADE`. (The old one-liner implied `bundle destroy` was sufficient — it isn't.)

### Added — `scripts/grant_viewers.py` (audience access for the About-page deep-links)
- Grants a **user / group / service principal** view-level access across every object the About-page "Under the hood" panel deep-links to — UC (`USE`/`SELECT`/`EXECUTE`/`READ VOLUME` via SQL GRANT), DLT pipeline (`CAN_VIEW`), job (`CAN_VIEW`), MLflow experiments (`CAN_READ`, scoped to the target's deploy path), forecast serving-endpoints (`CAN_QUERY`), KA + MAS Agent-Bricks tiles (`knowledge-assistants` / `supervisor-agents`, `CAN_QUERY`), and the Genie space (`CAN_RUN`). Permission levels + object types verified via `databricks permissions get-permission-levels`. Principal type auto-detects (`@`→user, UUID→service-principal, else group) — handles the DAIS booth's user-fronting service principal. Dry-run by default. DEPLOY.md "Grant the audience" section documents it.

## [2026-06-04]

Deploy-config hygiene: replace the single mutable `.env.bundle` (+ its in-place `HARNESS_TYPE` schema-mutation conditional) with **one explicit `.env.bundle.<target>` file per deploy target**. The old shared-file model meant whichever coords were `source`d last won — the root cause of past wrong-schema / SQL-403 drift when switching between the live and sandbox/harness targets. The per-target convention is the foundation for clean, repeatable from-scratch deploys (e.g. rehearsing a blank workspace).

### Changed — per-target `.env.bundle.<target>` deploy-config convention
- **`.gitignore`** — `.env.bundle` exact-match widened to `.env.bundle` + `.env.bundle.*` with `!.env.bundle.example`, so every per-target file (`.env.bundle.gsphere`, `.env.bundle.gsphere_from_source_e2e`, …) is ignored while the committed template stays tracked. (Previously the exact-match left `.env.bundle.<target>` files committable — a workspace-coord leak risk.)
- **`.env.bundle.example`** rewritten around the one-file-per-target model: name = the `databricks.yml` target key; `source .env.bundle.<target> && databricks bundle deploy -t <target>` (name parity); the `HARNESS_TYPE` conditional removed in favor of each file setting `BUNDLE_VAR_schema` / `BUNDLE_VAR_harness_suffix` explicitly. Internal-history dates stripped per the external-audience asset convention.
- **Docs propagated** — `DEPLOY.md` (Step 2, deploy steps, workspace-linkage diagram, the whole harness-targets section, Scenario A/B), `README.md`, `App/README.md`, `REPO_LAYOUT.md`, `docs/internal-setup.md`, `CONTRIBUTING.md` all updated from `.env.bundle` → `.env.bundle.<target>`. (Historical CHANGELOG entries below are left intact — they document the prior state at their release dates.)
- **`databricks.yml` + `databricks.yml.example` comment refresh** — variable/target comments that narrated the removed `HARNESS_TYPE` conditional now describe the per-target `.env.bundle.<target>` model (each harness target sets `BUNDLE_VAR_schema` + `BUNDLE_VAR_harness_suffix` in its own file). `.example` uses its `your_workspace_target*` naming.
- **Code-comment refresh** — stale `.env.bundle` / `HARNESS_TYPE` references in `scripts/render_app_yaml.py`, `scripts/grant_app_sp.py`, `Data_DataGen_ModelForecast/07_deploy_serving_endpoints.py`, and `02_ingest_real_baseline.py` updated to `.env.bundle.<target>`. Repo-wide verified: zero stale bare `.env.bundle` / `HARNESS_TYPE` outside intentional prose. (15 files total.)

## [2026-06-03]

Cross-referencing drill-downs across the three operator views, an About-page platform overview, chart legibility polish, a Device-error heatmap **metric-scope toggle** (In-incident ⇄ Fleet-wide) with a tuned color curve, an About-page **real-world-extrapolation** note, dependency-security bumps, and a public-repo hygiene pass that turns the committed `app.yaml` into a generic template. Advances GitHub **#2** (app display update — device/coach tabs + about info) and **#5** (Coach on real patient data) — both close when this branch reaches `main`.

### Added — Device-error heatmap metric-scope toggle (triage ⇄ fleet-wide) + real-world-extrapolation note
- **Metric-scope toggle** on Device Support's *Device Error by Firmware × Day* heatmap: **In-incident (triage)** — peak fault severity during the incident window (the existing ~40 mg/dL signal; default) — vs **Fleet-wide (compliance)** — the all-readings average per firmware-day, where the ~3 h fault dilutes into the day and severity is honestly masked. Reuses the MAE-timeline's affected-vs-fleet-wide vocabulary. `getFirmwareLifecycle()` now also returns `maeFleet` (the unconditioned `AVG(|observed − true|)`) alongside the in-incident `mae` — non-breaking for the Coach / Firmware-Lifecycle consumers that read `mae`.
- **Color curve tuned** (`getMaeColor` γ0.7): the emerald→amber→red ramp is bent so clean firmware-days gain visible green→yellow-green separation (real firmware baseline-noise gradient) without pushing a clean day into amber/red. The anchor stays in-incident-based in **both** scopes, so Fleet-wide renders honestly low/green rather than re-stretched to fake a fault. Heatmap subtitle nudged below the title/toggle row.
- **About → "What's simulated vs real"** gains a *"How this extrapolates to real devices"* paragraph: a fielded CGM fleet has no ground-truth reference, so the same calibration drift is monitored from observed readings alone via **cohort distribution divergence** (+ sparse fingerstick/lab MARD checks + per-lot sensor-QC telemetry); the operator views stay identical, only the cell metric swaps from error-vs-truth → distribution-divergence. Frames the production path for the DAIS narrative.

### Fixed — MARD terminology in Metrics Explained
- A baseline noise magnitude was mislabeled `~5.8 mg/dL MARD`; **MARD** is a *percentage* (mean absolute relative difference), so the mg/dL figure is a mean-absolute-**error**. Corrected to `~5.8 mg/dL baseline mean absolute error`. (The datagen MARD references in `_firmware_spec.py` / `05_*.py` already use `%` correctly — verified the mislabel was confined to this one user-facing line.)

### Added — patient ↔ device ↔ fleet drill-downs (closes the detect → diagnose → assess loop in-app)
- **Calibration Drift matrix → Population Risk.** Faulted drift cells on the Firmware Lifecycle page are clickable → Population Risk pre-filtered to that device model (`?model=`), with **✕ show all** to clear. Self-contained navigation (no external hop) for booth demos. (`8b1c452`)
- **Device ↔ Coach cross-links.** Device Support's Patient cell links to that patient's Diabetes Coach view (`9d88dc4`); Coach's device panel links to Device Support **focused on that device** with a status-aware honest reading (in-range vs OOR), overriding the OOR/3h gate so any device can be inspected (`207bb3e`).
- These wire #2's device/coach tabs together and exercise #5's real per-patient data.

### Added — About "Under the hood" platform panel + overview link
- About page gains a **Data → ML/AI → Agentic** platform-plumbing panel: each node deep-links into the deploying workspace (catalog, DLT pipeline, model serving, MAS/KA endpoints, Genie space) from `/api/config`, with accurate **Agent Bricks (KA + MAS) vs AI/BI Genie** taxonomy, a combined hero, and the glucose-ring logo beside the paragraph that explains it + embedded official Databricks links. (`406314d`)
- The overview word **"control tower"** links to Metrics Explained's *"Why this monitoring stack matters"* framing (`#me-why-monitoring`). (`8b1c452`)

### Changed — chart legibility
- **Firmware MAE timeline**: smaller axis / tick / value / legend fonts; y-axis title re-centred on the full SVG height (it was clipping at the top in the short plot band); trimmed the trailing whitespace below the legend. **Calibration Drift heatmap**: larger date headers, direction sublabels, and footer legend. (`8b1c452`)
- Firmware device-error **green → amber → red gradient** + half-open join dup-fix + Diagnose-page consolidation. (`0da9cf5`)

### Security — dependency bumps (Dependabot)
- `flask` → 3.1.3, `requests` → 2.33.0, `react-router-dom` → 6.30.3 (both HIGH alerts cleared); build-only `esbuild`/`vite`/`picomatch` deferred (dev-time only, no runtime exposure). Also fixed `render_app_yaml.py --ka-endpoint` to patch the `KA_ENDPOINT_NAME` env var, not just the resource binding (the env value had stayed stale). (`d2ec3dd`)

### Changed — committed `app.yaml` is now a generic template (public-repo hygiene)
- The committed `App/databricks/app.yaml` no longer ships one workspace's real catalog / warehouse / serving-endpoint / Genie IDs. Workspace-specific env values are **blank** (`CATALOG_NAME` → `your_workspace_catalog`, `WAREHOUSE_ID` / `SETUP_JOB_ID` / `ENDPOINT_NAME` / `KA_ENDPOINT_NAME` / `GENIE_SPACE_ID` → `""`) and the `resources:` bindings use placeholders (`your-mas-endpoint`, `your-ka-endpoint`, `your-warehouse-id`, `your-genie-space-id`). This is safe because **every** deploy (prod or sandbox) runs `scripts/render_app_yaml.py` first, which rewrites these per-target — Databricks Apps `app.yaml` env `value:` fields are literal strings that `bundle deploy` does **not** interpolate, so render is the only substitution path. `FM_ENDPOINT` (a global foundation-model name) and `SCHEMA_NAME` keep their workspace-agnostic defaults. `DEPLOY.md` updated (a stale "the live ones in app.yaml are …" example pointed at the removed IDs).

### Docs
- Repo-wide README/MD accuracy audit — corrected drift in mermaid diagrams, task counts, `dist`→`static` build-output paths, the firmware-version count, and the deep-link config table. (`34b71c4`)
- `DEPLOY.md`: the app-SP grant step (`scripts/grant_app_sp.py`) now explicitly covers the **fast-iteration bundle redeploy** — a bare `bundle run glucosphere_app` that skips the `glucosphere_full_setup` job (e.g. shipping a UI tweak) leaves the app SP ungranted (403 on every query), because the `09_grant_app_permissions.py` task only runs inside the setup job. Previously the doc framed this as a standalone-A/B-app-only concern.

---

## [2026-06-02]

Deploy-tooling ergonomics for side-by-side sandbox deployments, plus an end-to-end `from_source` validation of the whole Issue-#2 branch ahead of the PR to `main`.

### Fixed — firmware-boundary row duplication in the gold join (latent since the buildathon)
- The gold reading→firmware join in `transformations.sql` used an **inclusive** `a.time BETWEEN c.start_time AND c.end_time`. Because each firmware interval's `end_time` equals the next interval's `start_time` (the telemetry generator builds them via `lead(start_time)`), a reading at the *exact* firmware-transition instant matched **both** adjacent intervals and was duplicated — one extra `gold_patient_device_readings` row per device per firmware change. **Latent since the buildathon** (commit `d0bcf7c`, 2026-01-29): with the original 3-version rollout (`3.14 → 4.0 → 4.1`, 2 transitions) it silently duplicated ~2,000 rows; it surfaced only now because the 4-version rollout (`3.14 → 4.0 → 4.0.3 → 4.1`, 3 transitions → 3,000 dup rows = 1,000 patients × 3) **plus** a new firmware-cohort sanity check made it structurally visible — at the incident boundary the duplicate lands on the *prior* firmware. Tiny in aggregate (~0.15% of ~1.98M rows) so it never visibly moved a metric, but it fanned out every firmware-joined query (heatmap, calibration drift, roster). Fixed to a half-open **`a.time >= c.start_time AND a.time < c.end_time`** join so each reading matches exactly one interval (the final interval's `end_time` is a far-future sentinel, so all real readings are still admitted). The `getFirmwareLifecycle` boundary-guard comment in `databricksSQL.js` was updated to note the dup is now fixed at source (the guard remains as defense-in-depth). New AGENTS.md §9 captures the general lesson (distrust "it's always worked" in consolidated legacy code).

### Changed — free-name harness Apps via `${var.app_name}`
- The three harness targets (`gsphere_synth_e2e`, `gsphere_from_table_e2e`, `gsphere_from_source_e2e`) previously hardcoded the App resource `name:` to a composed string (`${var.app_basename}-<mode>-e2e-${var.dev_initials}`, e.g. `glucosphere-source-e2e-mmt`), so `BUNDLE_VAR_app_name` was silently ignored on the sandbox targets. Each harness `resources.apps.glucosphere_app.name` now references **`${var.app_name}`** (matching the production `gsphere` target, which already did). The per-target `variables.app_name` keeps the old composed string as its **default**, so:
  - **unset** → identical name to before (back-compat);
  - **`export BUNDLE_VAR_app_name=gsphere-v0-1`** → App deploys under that free name, enabling multiple independent sandbox copies (`gsphere-v0-1`, `-v0-2`, …) to coexist. This works because env-var `BUNDLE_VAR_*` outranks a per-target `variables:` default in [DABs variable precedence](https://docs.databricks.com/aws/en/dev-tools/bundles/variables) (command-line `--var` > `BUNDLE_VAR_*` env > `variable-overrides.json` > target default > top-level default).
- Mirrored in `databricks.yml`, `databricks.yml.example`, and an updated `.env.bundle.example` example line. App names remain 2–30 chars, lowercase/digits/hyphens. Production `glucosphere-app` is untouched (`${var.app_name}` default).

### Fixed — deterministic `device_model` (cohort gating no longer breaks on fresh deploys)
- `device_model` was assigned three independent random ways (registry positional `np.random.choice`, telemetry `rand(seed=42)`, and `05`'s read-registry-or-random fallback). On a fresh deploy `05` runs before `raw_patient_registry` exists, so the random fallback fired and biased **all six** device models in both directions — instead of the intended 4/6 (Alpha/Gamma over-read, Beta/Delta under-read, Epsilon/Zeta clean). Now `device_model` is a deterministic `md5(patient_id)` bucket defined once in a shared `_device_model_spec` (`%run` by `05` + the registry + the telemetry generator) — identical everywhere, no read-ordering dependency, no fallback. Registry patient↔device pairing fixed (was zipped from two separate non-deterministic `distinct().toPandas()` orders). `data_sanity_checks` gains three cohort-gating checks that fail the run if this regresses. Validated on a fresh `from_source` sandbox: +cohort = Alpha/Gamma only, −cohort = Beta/Delta only, Epsilon/Zeta clean.

### Fixed — `glucose_out_of_range` is purely glucose-based
- `transformations.sql` defined the flag as `... when incident_type is null then 0 else 1`, which force-flagged **every** incident reading out-of-range regardless of its glucose — inflating every OOR-rate panel and contradicting the flag's own documented meaning (Genie + Metrics-Explained both describe it as "outside 70–180"). Now `glucose < 70 OR glucose > 180`, consistent with `event_type` and the docs (verified: in-incident OOR dropped from a forced 100% to the real ~42%).

### Changed — Device Support: Device Error by Firmware × Day heatmap
- Replaced the muddy model×firmware out-of-range-**rate** heatmap (diluted to ~28–38% across all models by the real HUPA-UCM baseline, so it couldn't isolate the fault) with a **firmware × day device-error** heatmap (`mean |observed − true| mg/dL`, reusing `getFirmwareLifecycle`): FW 4.0 lights up on the incident days, 3.14/4.1 stay clean. Clean cells render green (matching the legend), faults red; firmware-days with no data are N/A. Panel flex-fills to balance the Calibration Drift column. Tour + Metrics-Explained updated to match. A roadmap caption flags the richer per-firmware drift **gradient** to come (a data-gen follow-up).

### Added — `AGENTS.md` + `CLAUDE.md`
- Repo operating principles for AI/human contributors: data-gen determinism (synthetic attributes as deterministic functions of `patient_id`), enforce invariants in the sanity gate, fix-at-source (a column's definition must match its docs), don't mutate shared data for a visualization, validate on a sandbox not the frozen demo, app-deploy hygiene (pin the app name; render before deploy), clinical honesty (rates not counts), and the campsite rule (leave it better; keep this file living). `CLAUDE.md` points to `AGENTS.md`.

### Changed — App UI copy
- First-visit welcome modal CTA relabeled **"Take the 60-second tour" → "Take a guided tour"** (`AboutModal.jsx`). The button opens the guided tour's **Quick (4-step) / Full (10-step) chooser** (no preset variant), so the old "60-second" label under-described what it launches; the new copy matches the sibling "Take a tour" launchers in the nav rail + landing header. Static bundle rebuilt.

### Validated — end-to-end `from_source` (PR pre-merge)
- Full setup-job run on an **isolated sandbox** (`gsphere_from_source_e2e` → `mmt_aws_usw2_catalog.glucosphere_from_source_e2e`, app `gsphere-v0-1` via the free-naming above) — all 16 active tasks **SUCCESS** (synthetic branch correctly EXCLUDED), incl. the `data_sanity_checks` gate passing on the real HUPA-UCM path. Gold `gold_patient_device_readings`: glucose range exactly **[40.0, 400.0]**, **1,000** patients, ~1.98M readings. App came up **HTTP 200**, `/api/config` reporting the correct `from_source` provenance + sandbox catalog/schema + resolved Genie space. Confirms the whole Issue-#2 branch deploys, runs, and serves on a fresh workspace. *(Note: device→bias cohorts are random in this run — the known determinism follow-up, not a blocker.)*

## [2026-06-01]

Clinical data-plausibility hardening + near-term-forecast coherence + a sanity gate, surfaced by a pre-demo audit. Fixes live in the data-gen notebooks (apply on the next pipeline run; re-run against the live `from_source` baseline). A full table backup is taken before any re-run.

### Changed — App UI: device-fault prominence, layout, guided tour (app-query-only; no data/pipeline change)
- **Calibration Drift panel (Device Support → Population Overview):** new panel showing mean `|observed − true|` mg/dL by device model × incident window — the device fault at its true **±40** (Window 1 over-read Alpha/Gamma, Window 2 under-read Beta/Delta, 300 devices each; Epsilon/Zeta clean). It isolates the fault where the whole-window out-of-range rate dilutes it (real HUPA-UCM baseline is ~31–39% OOR even on healthy devices, so a 3-hour fault washes out). New `getCalibrationDrift()` over `pseudo_incident_7d_labeled` ⋈ `silver_patient_registry`.
- **Population Overview re-layout:** three equal columns — Out-of-Range heatmap · Calibration Drift · Device Pattern Alerts (Regional Distribution dropped; its geo detail survives in Pattern Alerts' per-row region). OOR colorbar moved below the heatmap (horizontal). Added a **dynamic baseline/dilution note** whose number + provenance wording adapt to the deployment's `baseline_source` (real HUPA-UCM vs synthetic vs from_table).
- **Firmware Lifecycle MAE → in-incident:** the chart now scopes MAE to the affected (in-incident) readings, so the faulty firmware shows its true **~40 mg/dL** instead of a whole-day-diluted ~3.6; clean firmwares stay ~0 (a boundary-reading guard prevents the prior firmware from false-spiking on the rollout day). Faulty-firmware detection + the **"→ ACT: flag for rollback" card** restored (dilution had pushed the daily mean below the alert threshold).
- **Out-of-Range table:** a "click any row" hint surfaces the previously-hidden row drill-in + AI device analysis.
- **Guided tour:** a **Quick (4-step) / Full (10-step) chooser** (A/B-ready — variant is a parameter); the Full walkthrough covers every panel incl. drift, the drill-in table, firmware ACT, population risk, and the AI assistant; the tour now returns to the landing page when done.

### Fixed — clinical data plausibility (latent since the buildathon)
- **Glucose physiological range (both ends, two layers):** the bidirectional incident sim (`05`) applied the ±40 calibration bias with no clamp. Under-read drove readings to 0/negative (real baseline: 32 readings ≤0, 346 <20 mg/dL); and real-baseline hyperglycemia exceeded the CGM ceiling (~1,830 readings >400, max ~448 mg/dL). A real CGM reports "LO" below 40 and "HI" above 400, so **device-observed** glucose can never fall outside [40, 400]. Now clamps the **whole** `glucose_observed` column to **[40, 400]** at the source (`05`; `06` for parity, matching the `01:147` / `04:1006` clamps `05` never inherited), **plus a DLT-silver backstop** (`transformations.sql`: `greatest(least(glucose_observed, 400), 40) as glucose`) so the gold table the app reads is guaranteed physiological regardless of upstream path. `glucose_true` is left unclamped — the underlying physiological value can exceed 400; only the device reading is capped.
- **Demographics — diagnosis by age:** the patient-registry generator drew `patient_diagnosis` independently of `birth_year`, producing clinically-impossible combinations (Type 2 under 10, gestational over 55 / under 18). Now **age-conditioned**: T1D any age · T2D adult-onset (≥18) · gestational childbearing-age only (18–50). Population mix preserved (~T1D 41 / T2D 50 / gestational 8 — a CGM-monitored-fleet skew, since CGM is standard-of-care for T1D).
- **Near-term forecast anchor:** `fleet_forecast_incident` was anchored on a random mid-timeline (day 3–5) point, so the Coach "Now (observed)" disagreed with the chart's latest reading (e.g. 94 vs ~40). Now anchored on each patient's **latest reading** — genuinely near-term and consistent with the 7-day chart. Predictions clamped to [40, 400]. Coach panel relabeled **"Forecast baseline"** + a "batch run, not a live tick" note (honest framing; pairs with the streaming roadmap).

### Added — clinical-plausibility sanity gate
- `Data_DataGen_ModelForecast/utils/data_sanity_checks.py`, wired into the setup-job DAG as `data_sanity_checks` (gates the intelligence/app layer). **Fails the run** if any clinically-impossible record reaches gold — T2D under 13, implausible gestational age, glucose outside [40, 400], or a patient with no forecast row — so implausible data can never silently reach the app/demo again.

### Validated — live `from_source` re-run
- Full-pipeline re-run against the live `from_source` (real HUPA-UCM) baseline **passed the gate** end-to-end. Confirmed on `gold_patient_device_readings`: glucose range exactly **[40.0, 400.0]** (0 readings outside, ~1.98M readings), High-Risk tile = **176** patients (`<54 OR >250` in the last 3h), firmware **4.0 = 65.8%** out-of-range vs 4.1/3.14 ≈ 34% (the rate view isolates the faulty firmware), **1,000** patients. Demographics + forecast checks clean.

---

## [2026-05-31]

Issue #2 — App UI: control-tower redesign. A front-door app shell + Device Support overhaul, built and validated on an **isolated standalone app** (`glucosphere-app-v0-2`) for side-by-side comparison against the existing app, which is left untouched. Shares the same live governed data; no backend/pipeline changes.

### Added — v0-3 / v0-4 batch (real Coach · assistant engine switch · naming unification)

Built + validated on further isolated standalone apps (`glucosphere-app-v0-3`, then `glucosphere-app-v0-4`); live app + v0-2 untouched. Same live governed data; no pipeline changes.

- **Diabetes Coach — real per-patient view** (search, random/deep-link default, demographics/KPIs from `silver_patient_registry`, real near-term 15/30-min forecast from `fleet_forecast_incident`, masked-severity alert for under-read-during-hyper, 7-day observed-vs-true glucose timeseries with incident shading). Closes #5.
- **Switchable assistant engine** (`/api/assist`) — a fast app-side **router** (default): one direct call to **Genie** (data) / **Knowledge Assistant** (clinical) / a **foundation model** (`databricks-claude-sonnet-4-6`, device reasoning + fleet-stats enrichment); with a live ⚡ Fast / 🤖 MAS header toggle (localStorage) to the Multi-Agent Supervisor for A/B. Reliable 6–15s vs the MAS's erratic 17s→>300s-under-load (which trips the ~300s Apps gateway → 502/504). MAS endpoint preserved/reversible. New `GlobalAssistant` reset-chat. SP-grant helper `scripts/grant_app_sp.py`.
- **Chart hover read-outs** (`ChartTooltip.jsx`) on the Coach 24h/7-day profile, Firmware MAE, and Population cohort charts.
- **Naming unified** → **Glucosphere** (one product name) · *CGM Stream Intelligence* (descriptor; "GlucoStream" = its contraction/feed nickname) · *fleet control tower* (one metaphor, was split with "command center"). Logo links home.

### Fixed — v0-3 / v0-4 batch

- **Data integrity:** `device_model`/`region` now read from `silver_patient_registry` as SSOT across roster + Device-Support heatmap/alerts (was disagreeing with gold for some patients); roster %hypo/%hyper computed over the incident window (was diluted over the whole 7-day window).
- **Coach back button** returns to the originating page (Population Risk / rail / Home) via history, not always Home.
- **Docs/correctness:** Metrics Explained now distinguishes the **two MAEs** — model-monitoring forecast error (`|pred − actual|`, the ~3.8/5.9 clean → ~38 incident headline) vs the landing chart's device-error proxy (`ABS(glucose_observed − glucose_true) + 5.0`); "what's simulated vs real" provenance made mode-agnostic (real-by-default; synthetic mode honest).

### Fixed — metric honesty (counts → rates)

Cross-group fleet comparisons now report **rates (% of readings out-of-range)** instead of raw **counts**. `gold_patient_device_readings` is one row per reading (~288/patient/day), so a raw `COUNT` ranks groups by data *volume*, not clinical severity or device quality — and can invert the picture (the smallest cohort often has the highest rate). The rate framing is **data-agnostic** (correct on the real *and* synthetic baselines); only the absolute numbers differ by baseline.

- **Landing "High-Risk Alerts"** — was `COUNT(DISTINCT patient WHERE any <70/>180 in 3h)`; now the Battelino level-2 critical bands (`<54 OR >250`). *(On the real HUPA-UCM baseline this moved the tile from 517 → 176; synthetic skews far lower.)*
- **Coach per-patient risk band** — symmetric Battelino scheme (very-low `<54` / very-high `>250` escalate to HIGH; ⚠ hypo/hyper flags) instead of TIR-only, which never escalated dangerous hypoglycemia.
- **Firmware × model heatmap** (`getDeviceHeatmapData`) — `AVG(glucose_out_of_range)*100` rate per cell instead of a raw event count. *(On the real baseline this flipped the apparent "worst firmware" from 3.14 — a volume artifact at 1.59M readings — to 4.0, the actual fault: 66% out-of-range, and 100% of firmware-4.0 devices are the injected-incident cohort. The heatmap now agrees with the already-rate-based Device Pattern Alerts panel.)*
- **Device-readings table** — glucose value colors by clinical severity (`<54`/`>250` → rose, mild out-of-range → amber), matching the Range badge + risk score (was `<70 ? amber : rose`, which mis-colored critical lows).
- **CGM Genie space instructions** — steer cross-group questions to rates, Battelino bands for "high risk", and data-completeness (not glucose excursions) for device-health; corrected a stale column-name list in the space's data-context instruction.

### Added

- **Persistent left nav rail** (`App/src/components/AppShell.jsx` + `NavRail.jsx`) — collapsed icon strip that expands on hover and can be **pinned open** (choice persisted in `localStorage`); role entries (Device Support / Diabetes Coach) grouped under a "By role" label; replaces the old bottom persona cards. A "Take a tour" entry reprises the guided walkthrough.
- **Glucosphere brand mark** (`BrandMark.jsx`) — a glucose pyranose-ring SVG (the sugar molecule a CGM measures) with a live-reading sensor node, used across the rail, page headers, and About; a "The mark" explainer added to the About page.
- **About page** (`/about`) — platform-vs-product naming, real-vs-simulated data framing, repo link, and role quick-links.
- **Roadmap page** (`/roadmap`) — the detect·diagnose·assess "fuller control-tower views" preview trio, moved off the operational landing into its own page (rail entry).
- **Guided Tour** — no-dependency coachmarks keyed to the detect→diagnose→assess pitch beats; first-visit intro modal; replayable from the rail.
- **Regional Distribution map** (Device Support) — stylized SVG region bubbles sized by monitored footprint and colored by out-of-range volume, from a region-aggregate query (no map dependency).

### Changed

- **Landing reframed as a neutral command-center front door** — hero metrics → recent incident analysis; incident charts compacted to a left-header + responsive-SVG panel layout; verbose chart legends trimmed (detail kept in each chart's subtitle); redundant bottom "Quick Access by Role" cards removed (the rail is the role nav).
- **Diabetes Coach icon** stethoscope → heart-handshake (coaching, not clinical); "Other Dashboards" placeholder removed from Metrics Explained; glucose-range readout spacing fixed.
- **Device Support "Population Overview"** is now three equal-height, dynamically balanced panels: out-of-range **heatmap** (with a vertical colorbar) · **regional map** · ranked **device-pattern alerts**.

### Added (v0-3 batch — live Roadmap views, real Coach, unified assistant)

Built + validated on a second isolated standalone app (`glucosphere-app-v0-3`), leaving `v0-2` frozen as a stable demo anchor. Same live governed data; no backend/pipeline changes.

- **Roadmap previews promoted to live views** — **Firmware Lifecycle** (`/firmware-lifecycle`, ② diagnose: device calibration MAE by firmware version over time) + **Population Risk** (`/population-risk`, ③ assess: hypo/hyper exposure by cohort) + an affected-patients/devices **outreach roster** with a "send to triage queue" handoff. All via the existing SQL path — no new backend, no Lakebase.
- **Diabetes Coach — real per-patient view + working patient search** (`getPatientList` / `getPatientDetail` in `DiabetesCoachDashboard/queries.js`). Replaces the hardcoded "Sarah K." demo panel: live typeahead over the simulated `PSEUDO_*` cohort; per-patient demographics (age/diagnosis/device from `silver_patient_registry`), observed-window KPIs (avg glucose / TIR / hypo / CV), a real 24-hour glucose profile, and a derived-observations list — all from governed tables. **Closes #5.** Patient input is allow-listed before SQL interpolation (injection guard).
- **Near-term glucose forecast** (Coach) — replaces the non-credible "72-Hour Risk Forecast" with the real XGBoost **15/30-min** predictions (`fleet_forecast_incident.pred_15m/pred_30m`), shown as predicted CGM value + Δ vs now + in-range/hypo/hyper classification. (60-min horizon is a logged modeling follow-up.)
- **Unified global assistant** (`GlobalAssistant.jsx`, spec D4) — one shell-mounted assistant (FAB → slide-over) on every page, with two modes: **Device support** (Multi-Agent Supervisor, markdown answers) and **CGM data** (Genie, structured table + SQL + follow-ups preserved). Replaces and removes the two former page-local chats (Device Support inline panel + Coach inline Genie box); `AgentChatInterface.jsx` retired.

### Planned / follow-ups (not yet built)

- **Ongoing 5-min MAE monitoring** — continuous device-accuracy detection (rolling MAE → alert table); pairs with Lakebase alert state + the live-alert card.
- **Regional distribution**: optional toggle to break the view down by device type.
- **Light/dark theming** via semantic CSS tokens.
- **Interactive brand mark** — the glucose ring's branches as navigation links to the different views.
- **Guided Tour** — rework + extend the narrative to the new per-patient Coach view, the live Firmware/Population views, and the global assistant.

## [2026-05-30]

DABs target generalization: live target renamed `mmt_aws_usw2` → `gsphere` (workspace-agnostic logical name) with `mode: development` for visual parity with harness deploys. Workspace housekeeping: orphaned harness deploys + pre-cutover catalog schemas + the historical `hls_amer` target stanza all cleaned up. New explicit linkage diagram (`.env.bundle` → `~/.databrickscfg` profile → workspace selection) added to `databricks.yml` and `DEPLOY.md`. New full `databricks.yml.example` template mirror.

### Changed

- **Live target renamed** `mmt_aws_usw2` → `gsphere` (and harness variants `gsphere_synth_e2e` / `gsphere_from_table_e2e` / `gsphere_from_source_e2e`). The target key is a logical deploy label, not a workspace identifier — workspace selection has been profile-driven since `75df678`. The rename clarifies intent for external deployers. Resources auto-suffix on `${bundle.target}` → `glucosphere-X-gsphere` instead of `glucosphere-X-mmt_aws_usw2`. Uses the existing `gsphere` alias already documented in `databricks.yml:47` for `app_basename`.
- **`mode: development` on live target** — parallel to harness targets. Auto-prefixes jobs/pipelines/warehouse with `[dev <deployer>]` in the Workflows UI. No functional impact: no schedules to pause, batch pipeline (no streaming dev-mode concerns), App/Genie/MAS/endpoints reference by ID (not name). Display name varies by deployer (`[dev may_merkletan]` vs `[dev justin_ward]`); acceptable for shared demo workspace. `mode: production` deferred until CI/CD service-principal + non-user-home workspace `root_path` are provisioned.
- **Comment block rewrites** in `databricks.yml` targets section: clarified linkage between `.env.bundle` profile and DABs workspace selection, documented `mode: development` choice, removed stale `{}` empty-body references.
- **`DEPLOY.md` rewrite**: added a "How workspace selection works (linkage diagram)" ASCII block at the top of "Target-specific notes" showing the `.env.bundle` → `~/.databrickscfg` profile → workspace host chain explicitly. Renamed all target references to `gsphere*`. Dropped the historical `hls_amer` section entirely.

### Removed

- **`hls_amer` target stanza** dropped from `databricks.yml` and DEPLOY.md (was historical / blocked per prior CHANGELOG; no longer in use; cross-workspace SP entanglement made the workspace permanently unusable for this project).

### Cleanup (workspace housekeeping)

- **Destroyed 3 harness bundle deploys** (`mmt_aws_usw2_{synth,from_table,from_source}_e2e`) — removed their jobs/pipelines/warehouses/apps from Workflows UI. The harness target stanzas remain in `databricks.yml` (now renamed `gsphere_*_e2e`); future regression runs are 1 command (`HARNESS_TYPE=<mode> source .env.bundle && databricks bundle deploy -t gsphere_<mode>_e2e`).
- **Dropped 6 orphaned UC schemas** across 2 catalogs:
  - `mmt_aws_usw2.glucosphere_synth_e2e` (Level B test data from PR-1 closeout)
  - `mmt_aws_usw2_catalog.{glucosphere_synth_e2e, glucosphere_from_table_e2e, glucosphere_from_source_e2e, glucosphere_dev, glucosphere_dev_compare_synth}` — pre-standalone-catalog-cutover artifacts
- **Deleted workspace-global harness resources** — `Glucosphere_{KA,Supervisor,Intelligence,Forecast_15min,Forecast_30min}_synth_e2e` tiles/space/endpoints.

### Live redeploy (Level-C-style destroy + redeploy under new gsphere name)

- **Destroyed live `mmt_aws_usw2`** completely (`bundle destroy --auto-approve`), dropped `mmt_aws_usw2.glucosphere` schema, deleted live KA/MAS tiles + Genie space + both forecast endpoints.
- **Redeployed under new `gsphere` target**: `bundle deploy -t gsphere` pass 1 (created infra stubs), `render_app_yaml.py --target gsphere` (discovered new warehouse_id + setup_job_id), `bundle deploy -t gsphere` pass 2, `bundle run glucosphere_full_setup -t gsphere` (~44 min — created fresh data + KA/MAS/Genie/forecast endpoints with new IDs), `render_app_yaml.py` again with new agent IDs, final `bundle deploy -t gsphere`, `bundle run glucosphere_app -t gsphere`.
- **End state**: 3 live workflow items in UI now prefixed `[dev <deployer>]`, named `glucosphere-{cgm-silver-gold,full-setup,distribution-comparison}-gsphere`. App `glucosphere-app` RUNNING. All 5 workspace-global resources (KA/MAS/Genie/2 forecast endpoints) fresh under the same canonical names (`Glucosphere_KA`, `Glucosphere_Supervisor`, `Glucosphere_Intelligence`, `Glucosphere_Forecast_15min`, `Glucosphere_Forecast_30min`).

### Added

- **`databricks.yml.example` full mirror template** (~688 lines, was 45). Now a complete adapt-and-rename reference for external deployers. Target keys substituted to `your_workspace_target*`. All bundle resources mirrored verbatim. Operators copy/rename → adapt `.env.bundle` → deploy.

---

## [2026-05-29]

Serverless GPU validation for `datagen_modeling` task + stratification
verification fix (Fix A*) + Optuna/GPU scaling notes.

**Note for reviewers**: today's changes affect ONLY the `datagen_modeling`
task (compute config + verification print logic + comment clarifications).
Downstream tasks (`incident_inference`, `deploy_model_endpoints`,
`run_dlt_pipeline`, `create_genie_ka_mas`, `check_post_endpoint_grants`,
`grant_app_permissions`, and the patient-device data tasks) are unchanged
and do not need to be re-run for this PR. The MLflow models produced by
GPU training are functionally equivalent to the CPU-trained ones (same
architecture, same hyperparams, same data).

### Added

- **Serverless GPU compute on `datagen_modeling` task** — added
  `compute.hardware_accelerator: GPU_1xA10` (GA option) to the task in
  `databricks.yml`, plus a new `gpu_default` environment with `client: "5"`
  (CPU `default` env keeps `client: "1"` for the other 15 tasks).
- **GPU/Optuna scaling notes** in `04_pseudo_data_forecast_modeling.py` (above
  the Optuna `Parallel(n_jobs=4)` block) and in `databricks.yml` (under the
  `compute` block comment) — explain that single-GPU GPU_1xA10 serializes the
  4-way parallel Optuna trials, and that GPU_8xH100 (Beta) would fan out 4 of
  the 8 H100s if `RUN_OPTUNA_TUNING="true"`.

### Fixed

- **Stratification verification compared wrong statistics ("Fix A\*")**:
  `04_pseudo_data_forecast_modeling.py` was comparing pseudo per-reading
  time-in-range (e.g. 6.5% hypo) against source per-patient-strata
  classification ratios (e.g. 18.2% hypo-prone patients). These are different
  statistics by construction — produced spurious FAIL warnings on runs whose
  underlying data was actually sound. Fix queries `baseline_val_tbl`
  (`baseline_for_validation_7d`) which is built from the EXACT sampled
  segments — strict apples-to-apples per-reading comparison, recomputed each
  run so it tracks dynamic source / demo_week_start / sampler state.
- **Print-statement clarity sweep** (lines 415, 495, 617, 696, 833, 842 of
  `04_*.py`): disambiguated all "match baseline distribution" / "source-derived
  ratios" framings to explicitly distinguish per-patient-strata classification
  (sampler intent) from per-reading time-in-range (verification metric). This
  removes the conceptual ambiguity that motivated the FAIL warnings.

### Verified

- **GPU compute validation on `mmt_aws_usw2` workspace**: empirical job runs
  confirm the GPU path works end-to-end —
  - CPU baseline (pre-GPU work): run `674492992118957`, `datagen_modeling`
    task duration **808.4 s (13.47 min)** on serverless CPU (client "1")
  - GPU run 1 (first GPU validation): run `291178450563756`, task duration
    **290.0 s (4.83 min)** on `GPU_1xA10` (client "5")
  - GPU run 2 (post-Fix-A\* rerun): run `283150645379656`, task duration
    **317.6 s (5.29 min)** on `GPU_1xA10` (client "5")
  - Empirical speedup vs serverless CPU: **~2.7x** (13.5 min → ~5 min)
- **MLflow `system/gpu_0_*` metrics logging** — verified via
  `/api/2.0/mlflow/runs/search` for both GPU runs. 5 GPU metric series:
  `gpu_0_utilization_percentage` (peak 75%), `gpu_0_memory_usage_megabytes`
  (peak 914.9 MB of A10's 24 GB = 3.8% used), `gpu_0_power_usage_watts`
  (peak 135.7 W), `gpu_0_power_usage_percentage`, `gpu_0_memory_usage_percentage`.
  Pre-fix runs had 0 GPU metric series — silent skip per MLflow's
  `_initialize_gpu_monitor` fallthrough (missing `nvidia-ml-py`).
- **Fix A\* verification produces PASS/PASS/PASS** for default `from_source`
  baseline mode — pre-deploy SQL probe against
  `mmt_aws_usw2.glucosphere.baseline_for_validation_7d` (via warehouse
  `glucosphere-warehouse-mmt_aws_usw2`) returned hypo 6.40% / normal 66.09% /
  hyper 27.51%; pseudo data was 6.5% / 65.9% / 27.6% — Δ 0.10% / 0.19% / 0.09%,
  all within tolerance bands (2% / 5% / 4%).

---

## [2026-05-28]

PR-to-main polish: cycle-2 regression fix + standardization sweep + UC Volume
rename (`landing_zone` → `pipeline_data`) + external-audience documentation
pass + legal/CI scaffold from `origin/main`. 34 commits on
`feature/dual-baseline-mmt-aws-usw2`.

### Fixed

- **Heatmap firmware variety regressed 3 → 2** (Device Support page). Root
  cause: `Create Raw Device Data.ipynb` hardcoded Jan 7-9 2026 firmware-event
  timestamps; `demo_week_start` auto-resolves to `today_utc - 6 days`, so May
  2026 data fell outside the Jan firmware windows, leaving only B1 and B5
  branches active. Fix derives the 4 firmware-event timestamps from
  `cfg.demo_week_start + timedelta` offsets (Day 3 + Day 5 of the demo
  window). Also dropped the dead duplicate Cell 1 (98-line copy of Cell 2's
  `make_device_firmware()`).
- **MetricsExplained PNG missing**. Silent `try/except` around 4 PNG saves in
  `05_incident_inference_bidirectional.py` swallowed write failures while
  task reported SUCCESS. Removed the try/except so failures throw. Added
  `CREATE VOLUME IF NOT EXISTS pipeline_data` guard before the first
  `dbutils.fs.mkdirs(_ASSET_DIR)` — surfaced a real DAG-ordering issue on
  fresh-schema deploys that the silent except had been masking.
- **`Create Raw Device Data.ipynb` missing `pyyaml`** added to the `%pip
  install` line (required by the Config-class loader).
- **GPU metrics in `04_pseudo_data_forecast_modeling.py`** — added
  `nvidia-ml-py` to the `%pip install` line. MLflow's `GPUMonitor` was
  silently failing to initialize because the NVML binding wasn't installed
  (CPU/memory still logged via `psutil`, but GPU stats never collected; per
  MLflow's `system_metrics_monitor._initialize_gpu_monitor()` the missing
  NVML is caught and skipped with a DEBUG-level log, hence the silent miss).
  The earlier print statement referenced the deprecated `nvidia-ml-py3`
  which was never actually in the install line. Replaced with current
  `nvidia-ml-py` per MLflow system-metrics docs; print statements
  corrected; dep table entry restored under the corrected package name.

### Changed

- **UC Volume rename `landing_zone` → `pipeline_data`** — semantic accuracy
  (volume holds raw parquet + rendered PNGs + WHO PDFs, not just landing
  files). Single-pass grep-clean rename across `databricks.yml`, all pipeline
  notebooks (01-09), `App/databricks/app.py`,
  `App/src/pages/MetricsExplained.jsx`, `09_grant_app_permissions.py`
  (`GRANT READ VOLUME ... pipeline_data`), `DEPLOY.md`, `REPO_LAYOUT.md`,
  `README.md`. Historical entries below retain `landing_zone` for accuracy
  of past-state record.
- **Widget standardization** — catalog/schema defaults + widget names +
  variable refs + `databricks.yml` `base_parameters` keys all unified to
  `CATALOG_NAME` / `SCHEMA_NAME` (UPPERCASE-with-`_NAME`-suffix). Touched 13
  `.py` files and 3 `.ipynb` files (`Create Raw Device Data.ipynb`, `Create
  Patient_Device Table.ipynb`, `Create Raw Patient_Registry Data.ipynb`)
  which previously used lowercase `catalog`/`schema` widget names. Default
  values now use placeholder `your_workspace_catalog` (was a mix of
  `glucosphere_catalog`, `hls_glucosphere`, `cgm`).
- **`DEMO_WEEK_START` override widget** added to `04_*.py`, `05_*.py`,
  `06_*.py`, `07_*.py`. Empty value falls back to the `databricks.yml`
  `DEMO_WEEK_START` parameter (`auto` or a specific date); non-empty value
  populates `widget_overrides["DEMO_WEEK_START"]` and feeds into the
  Config-class loader. Validated via one-off run with `notebook_params:
  {"DEMO_WEEK_START": "2026-05-01"}` — gold time range came back exactly
  `2026-05-01 → 2026-05-07` with 3 firmware values.
- **Smoke test extended 6 → 8 checks** — new `check_firmware_variety()`
  asserts `COUNT(DISTINCT firmware_version) >= 3` on
  `gold_patient_device_readings`; new `check_uc_asset_png()` fetches the
  MetricsExplained 4-panel PNG via the Files API (`GET
  /api/2.0/fs/files/Volumes/.../pipeline_data/incident_inference_assets/...`)
  using curl + auth token from `databricks auth describe` (the CLI's `api
  get` chokes on binary PNG bytes), validates HTTP 200 + PNG magic-bytes
  header. Catches both cycle-2 bug classes automatically next time.
- **Warehouse `auto_stop_mins: 10 → 30`** in
  `databricks.yml: resources.sql_warehouses.glucosphere_warehouse`. Reduces
  cold-start latency on the GlucoStream Intelligence landing page.
- **`README.md` repo title** `hls-glucosphere` → `Glucosphere` —
  external-audience cleanup. The `hls-` prefix was internal-tracking
  branding, not user-facing.
- **`README.md` Contributors section** rewritten as flowing narrative with
  per-person attribution. Two pre-Buildathon threads — (1) the Nov 4 2025
  MedTech Q4 QBR Hackathon (Jon Van Hofwegen, Sabrina Wang, Sumanth Ghanta,
  May Merkle-Tan) produced the data/ML foundations + MVP App with
  Multi-Agent Supervisor (MAS) agentic layer; (2) in parallel, Morgan
  Williams's prior customer-driven faulty-firmware device alert demo became
  the incident-simulation scaffolding. → Buildathon FY26Q4 Team 11 (Justin
  Ward, Morgan Williams, May Merkle-Tan, Nikita Kamraj, Sabrina Wang)
  integrated the two threads — May grounded the device story in real FDA
  recall context; Morgan integrated his prior demo into a pseudo-online
  DLT pipeline with firmware versions tracking the incident timeline;
  Justin led appification via the ai-dev-kit + React frontend + bundle
  scaffolding. → Post-Buildathon MVP tidy-up (Justin, May, Morgan).
- **README + DEPLOY runtime estimates** corrected to cycle-2-verified
  numbers (full `glucosphere_full_setup` job ~48 min).
- **External-audience cleanup pass** across `README.md`, `DEPLOY.md`, inline
  comments in `databricks.yml`, `08_genie_ka_mas.py`,
  `09_grant_app_permissions.py`, `03_compare_baseline_modes.py`, and widget
  descriptions. Stripped internal task numbers, workspace-specific
  catalog/schema examples, dated lapse notes, commit-ref pointers. Kept
  WHAT + WHY + override knobs.
- **`.env.bundle.example` profile placeholder** changed from
  `acme-aws-usw2` (fake-org style) to `your-workspace-profile` to match
  the `your_workspace_*` placeholder convention used elsewhere in the
  same reference example block (line 67: `your_workspace_catalog`).
- **Internal-reference comment cleanup** across `databricks.yml` +
  `DEPLOY.md`: stripped `(Plan's Commit F — #42)` from the Lakebase
  resource block; removed two `feedback_smallest_nonnegotiable_compute`
  Claude-memory-file references from warehouse + Lakebase sizing
  comments; dropped the `DEPLOY.md` "Memory + ref_notes to pre-load for
  Glucosphere context" subsection (entire block referenced
  `~/.claude/projects/...` paths, Claude memory file names, and
  gitignored `ref_notes/<latest-date>_end-of-day-snapshot.md` — all
  internal-only).
- **`databricks.yml` warehouse comment clarified**: explicit "Serverless
  SQL Warehouse" framing — `warehouse_type: PRO` +
  `enable_serverless_compute: true` is the canonical serverless
  combination (PRO = modern tier; CLASSIC = legacy non-serverless). The
  `PRO` value name historically reads as a paid-tier rather than
  serverless, so the comment now disambiguates.
- **`DEPLOY.md` "current active demo target" section** reframed:
  `mmt_aws_usw2` now labeled as the maintainer's deploy target with
  explicit external-deployer note pointing at
  `databricks.yml.example` for adding their own target stanza.
- **`App/README.md` cleanup**: stripped stale "Configuration Files"
  subsection (referenced non-existent `App/config/databricks_config_*.json`
  files); stripped stale "Documentation" subsection (referenced
  non-existent `App/docs/` folder with deployment guides /
  agent-integration / migration-notes / troubleshooting); replaced "Tech
  Stack" 4-line bullet block with a full **Dependencies used and their
  corresponding license information** table (matches the
  `Data_DataGen_ModelForecast/README.md` pattern) — frontend deps
  verified against local `node_modules/<pkg>/package.json` `license`
  fields; backend deps verified via local `dist-info/METADATA` (requests
  Apache-2.0) + upstream `pyproject.toml` (Flask BSD-3-Clause). Replaced
  the "For issues or questions, contact the HLS Glucosphere team"
  Support line with an AS-IS / no-warranty framing matching the
  repo-root `LICENSE.md`, pointing at GitHub Issues as the
  bug/feature-suggestion channel.
- **`Data_DataGen_ModelForecast/README.md`**: added a Python-runtime
  prose paragraph above the dependencies table — clarifies that
  notebooks run on Databricks Runtime's Python (`spark_version` set in
  `databricks.yml`) and only repo-root `scripts/` use the local Python
  3.11 (per `.python-version`).
- **Repo-root `README.md` restructure** — 309 lines → ~110 lines. The
  README is now a "lobby" / orientation doc; substantive detail lives
  next to the code that produces it.
  - **Data fidelity & baseline modes** (61 lines: baseline-mode table,
    clean-vs-incident model performance, column-level provenance,
    synthetic-vs-real distribution comparison) moved to new sibling
    [`Data_DataGen_ModelForecast/README_data_fidelity_baseline.md`](Data_DataGen_ModelForecast/README_data_fidelity_baseline.md).
    The repo-root README keeps a 4-line teaser + link; the existing
    `Data_DataGen_ModelForecast/README.md` adds a header cross-link to
    the new sibling.
  - **Architecture / Agent endpoints — Genie / KA / MAS deep-dive**
    (35 lines: endpoint table, MAS routing mermaid, routing examples)
    moved into [`App/README.md`](App/README.md)'s existing Architecture
    section as a new `### Agent endpoints — Genie / KA / MAS` subsection.
    The repo-root README keeps a 1-sentence summary + link.
  - **Repository structure** trimmed from a 53-line file-by-file tree
    to a 10-line top-level skeleton + link to the existing
    [`REPO_LAYOUT.md`](REPO_LAYOUT.md) (which already carries the full
    "I want to…" task index + workflow DAG + by-category file inventory).
  - **Getting started** trimmed from 85 lines (prereqs + 5 deploy
    subsections including variants, demo-week pin, verify-which-mode,
    distribution comparison) to a ~15-line canonical deploy snippet +
    prereqs paragraph + link to [`DEPLOY.md`](DEPLOY.md) for the full
    8-step walkthrough + variants + troubleshooting.
  - **See also** section consolidated and expanded — now includes
    pointers to `REPO_LAYOUT.md`, `DEPLOY.md`, both
    `Data_DataGen_ModelForecast` READMEs (the existing one + the new
    sibling), `App/README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
  - **Plugins + Contributors** sections kept verbatim — they're
    orientation-level content that belongs in the repo-root README.
- **`Data_DataGen_ModelForecast/README.md` "Figures (assets)" section
  moved** to the new sibling
  [`README_data_fidelity_baseline.md`](Data_DataGen_ModelForecast/README_data_fidelity_baseline.md).
  All 6 figures (baseline-vs-pseudo distribution, 15m/30m forecast
  accuracy, incident impact summary, fleet-wide MAE-breakdown,
  true-vs-observed glucose, 4-class distribution shift) are about
  data fidelity + model performance + distribution analysis, so
  they belong next to that content. The original location keeps a
  3-line pointer to the sibling section anchor.
- **`CONTRIBUTING.md`**: new "Keeping dependency tables current" section
  between "Branch + commit conventions" and "Updating the CHANGELOG".
  Documents the verify-license-then-update-table workflow + when to use
  prose-near-the-table for platform-provided deps (vs padding the table
  with non-declared items).
- **Dep table format — drop separate `Source / URL` column, embed source
  link on dependency name** (`App/README.md` frontend + backend tables,
  `Data_DataGen_ModelForecast/README.md` table). 4-col layout: Dependency
  | Where used | Why it's used | License. GitHub source repo linked on
  the bolded dep name where one exists; `nvidia-ml-py` links to PyPI
  because NVIDIA distributes only via PyPI (no public NVIDIA GitHub repo
  for these bindings).
- **Added "Note on package URLs and network reachability"** below the
  `Data_DataGen_ModelForecast` dep table, with one-line pointer notes
  under each `App/README.md` dep table. Context: some Databricks
  workspaces / corporate networks block direct egress to `pypi.org` /
  `files.pythonhosted.org` / `registry.npmjs.org`; this tightening
  accelerated after the LiteLLM PyPI supply-chain compromise of
  2026-03-24 (malicious versions 1.82.7/1.82.8 published via stolen
  publishing tokens via Trivy CI compromise). Note references PyPI's
  incident report + Databricks serverless egress-control docs +
  Databricks MLR-vs-DBR `nvidia-ml-py` preinstall difference.
- **Mermaid diagram in `App/README.md`** (MAS routing logic) — added
  `%%{init: {'theme': 'neutral'}}%%` directive for monochrome
  (grey/white) rendering instead of the default colored theme.
- **`Data_DataGen_ModelForecast/README.md` References section** —
  softened the citation for Nature Digital Medicine `s41746-021-00480-x`
  (Deng et al. 2021). Previous wording (added 2026-05-27) overclaimed:
  "informs the CGM-forecast modeling + MAE-based incident-evaluation
  methodology used". Corrected: the paper does **patient-specific deep
  learning via transfer learning** (CNN/GRU/SAN architectures
  fine-tuned per patient on ~83 hours of CGM data, 40 outpatients,
  MAE 13.53 mg/dL @ 30-min). Glucosphere takes a different path —
  fleet-level XGBoost on 1,000 pseudo-patients sampled from HUPA-UCM,
  15/30-min horizons, MAE 5.3/9.2 mg/dL clean — for demonstration
  simplicity. The paper is now framed as offering "alternative
  approaches for CGM monitoring and forecasting" + "guidance on
  relevant metrics of interest", not the methodology we implemented.

### Added

- **`databricks.yml.example`** (NEW, repo root) — target stanza pattern
  for external deployers, mirroring the `.env.bundle.example` template
  convention. Documents the live + harness target shapes and how to add
  your own without touching the maintainer's `hls_amer` / `mmt_aws_usw2`
  stanzas. Cross-referenced from `CONTRIBUTING.md` (new "Adapting for
  your own workspace" section) and `DEPLOY.md`.

- **`CONTRIBUTING.md`** (NEW, repo root) — invites external contributors
  with CLA scaffold prepended from `origin/main`'s
  `databricks-industry-solutions` Solution Accelerator template. Documents
  local-dev loop (`uv` + Databricks CLI), branch + PR conventions, and the
  CLA-on-first-PR pattern.
- **`LICENSE.md`**, **`NOTICE.md`**, **`SECURITY.md`**,
  **`.github/scripts/`**, **`.github/workflows/`** — cherry-picked from
  `origin/main` Solution Accelerator template scaffold. Resolves the
  unrelated-histories state between
  `feature/dual-baseline-mmt-aws-usw2` and `main` ahead of PR-to-main
  without restructuring `App/` or `Data_DataGen_ModelForecast/`.
- **`README.md` Architecture subsection** — Genie / KA / MAS endpoint
  distinction documented with a routing mermaid. NL-SQL → Genie space over
  gold tables; RAG over WHO PDF → KA endpoint; MAS supervisor routes
  clinical reasoning between them.
- **`DEPLOY.md` deploy-flow mermaid** at the top of the guide — visualizes
  the 7-stage flow (env setup → first deploy → render → second deploy →
  run pipeline → start app → smoke test).
- **`docs/internal-setup.md`** (NEW) — catalog naming convention for
  internal fevm workspaces + maintainer-set caveat. Split out of `README.md`
  to keep the main README external-facing while preserving the guidance for
  teammates deploying onto internal catalogs.

### Verified

- **Fresh-deploy `mmt_aws_usw2` end-to-end**: `bundle destroy` (bundle
  resources + `DROP SCHEMA CASCADE` + manual API cleanup of KA/MAS/Genie
  tiles + serving endpoints) → `bundle deploy` (pass 1) →
  `render_app_yaml.py` → `bundle deploy` (pass 2) → `bundle run
  glucosphere_full_setup` (full 15-task DAG) → `bundle run glucosphere_app`
  → `smoke_test.py`. Result: smoke 8/8 PASS.
- **Visual UI checks**: Metrics Explained → 4-panel comparison PNG renders
  via `/uc-assets/`; Device Support → heatmap shows 3 firmware columns
  (`3.14` / `4.0` / `4.1`) × 6 device models = 18 cells; GlucoStream
  Intelligence landing → all 3 panel plots render after warm warehouse.
- **`DEMO_WEEK_START` widget override path** validated end-to-end (see
  Changed above).

---

## [2026-05-27]

SSOT config + Path 2 bundle-managed warehouse + dead-code/config purge — single comprehensive commit (`eada716`, 32 files, +403/-2028 lines), pushed to origin. Consolidates the operator-facing config surface around `.env.bundle`, refactors App SQL routing to leverage a bundle-managed `sql_warehouses` resource, and purges verified-dead code/config across the repo.

### Added

- **`.env.bundle.example`** (NEW, repo root) — committed template for operator-owned `.env.bundle` (gitignored). Three required tokens: `BUNDLE_VAR_catalog`, `BUNDLE_VAR_schema`, `DATABRICKS_CONFIG_PROFILE`. Documents the deploy sequence (`source → render → deploy`) + a sanitized reference example with placeholder values.
- **`databricks.yml: resources.sql_warehouses.glucosphere_warehouse`** — bundle-managed serverless 2X-Small PRO warehouse, auto-stop 10 min. Name pattern `glucosphere-warehouse-${bundle.target}`. Smallest viable per `~/.claude/memory/feedback_smallest_nonnegotiable_compute.md`.
- **`Data_DataGen_ModelForecast/README.md` References section** — new at end of file. Cites Nature Digital Medicine `s41746-021-00480-x` as informing the CGM-forecast + MAE evaluation methodology used across `04_*` (training), `05_*` / `06_*` (inference), and `07_*` (serving). Replaces the bare URL comments previously floating in 05/06 near-empty cells.
- **Historical-baseline clarifying note in `05_*.py`** — explains that the `5.8 / 10.4 mg/dL` MAE values referenced throughout (intro, prints, chart `axhline` reference lines) are the published synthetic-trained baseline from `origin/hls-buildathon-main`, not the current run's dynamically-computed value. Points reader at the MAE analysis cells below for actual numbers per run.
- **`REPO_LAYOUT.md`** (NEW, repo root) — new-user repository navigation guide: "I want to…" tables (deploy / pipeline / App / architecture), by-category PR-shipped inventory, gitignored-vs-PR summary, Mermaid DAG of the `glucosphere_full_setup` job (16 tasks, verified against `databricks.yml`). Points readers at CHANGELOG as the canonical discoveries record (this file). README `See also` + DEPLOY preamble updated to cross-reference.

### Changed

- **SSOT config flow** — operator-facing values (catalog / schema / profile) now come from gitignored `.env.bundle` via `BUNDLE_VAR_*` env vars + `DATABRICKS_CONFIG_PROFILE`. Live target stanzas (`hls_amer`, `mmt_aws_usw2`) in `databricks.yml` reduced to `workspace.host:` only — operator-specific values no longer baked into the repo. Removed `default: true` from all targets; `-t <target>` is now always required.
- **App SQL routing — MCP → Statement Execution API** (`App/databricks/app.py /api/sql/query`). Reads `warehouse_id` from `WAREHOUSE_ID` env var (populated by `scripts/render_app_yaml.py` from the bundle-managed `sql_warehouses` resource). Response wrapped to preserve React-side `result.result.structuredContent` contract — `App/src/api/databricksSQL.js` unchanged. Resolves the runtime issue where MCP routing ignored `app.yaml`'s `resources.sql_warehouse` binding (verified via 4-pass e2e test, see `ref_notes/2026-05-26_warehouse-bundle-management-verification.md`).
- **`scripts/render_app_yaml.py` warehouse discovery** — replaced `vars_.get("warehouse_id")` with a `databricks warehouses list` query + `endswith` match on `glucosphere-warehouse-<target>`. Patches BOTH the new `WAREHOUSE_ID` env var AND the resource `sql_warehouse.id` binding in `App/databricks/app.yaml`.
- **`09_grant_app_permissions.py` warehouse discovery fallback** — new `BUNDLE_TARGET` widget (set by `databricks.yml` task base_param `${bundle.target}`). When `WAREHOUSE_ID` widget is empty, 09 queries `/api/2.0/sql/warehouses` and matches by deterministic suffix to find the bundle-managed warehouse, then grants `CAN_USE` to the App SP.
- **App rename** `glucosphere-dashboard` → `glucosphere-app` — `${var.app_name}` default, app resource key (`apps.glucosphere_app:` at 4 spots — top-level + 3 harness overrides), `09_*.py` widget default + SP-name example comment, `DEPLOY.md` references (3 spots), `App/databricks/app.yaml` description-text comment, top-level `README.md` inventory tree. Comment header reflects branding split: "App: Glucosphere App (front-end branding: 'GlucoStream Intelligence')".
- **Notebook rename** `04_pseudo_data_modeling.py` → `04_pseudo_data_forecast_modeling.py` — better describes the XGBoost-forecast-model-training role. 13 textual references updated across `databricks.yml`, `README.md`, `DEPLOY.md`, `Data_DataGen_ModelForecast/README.md`, `01_*.py`, `02_*.py`, `utils/validate_diabetes_data.py`.
- **`DEPLOY.md` Steps 2 + 6 reworked** — Step 2 now describes the `.env.bundle` workflow + the 6-variable contract (was 9 vars with hardcoded `warehouse_id` default). Step 6 documents the two-pass first-deploy pattern (deploy → render_app_yaml → deploy) for the bundle-managed warehouse flow.
- **`02_ingest_real_baseline.py` + `utils/validate_baseline_source.py` source-priority lists** — dropped the workspace-specific `glucosphere_dev` entry from the auto-detect candidate list. Now workspace-agnostic: harness schemas only (real-data harness → synth harness).
- **Public-repo audience pass on inline comments + widget descriptions** — trimmed internal task numbers (`#68`, `#74`), dates (`2026-05-26`), commit refs (`1db686e`), phase-roadmap notes (`Phase 2/4/5`), and fix labels (`C8/C14/C17/C18`) from `databricks.yml` harness target blocks. Added a new-user override tip pointing at `BUNDLE_VAR_*` env vars; restated the concurrent-deployer caveat as a behavior with a workaround instead of a forward-ticket pointer. Also removed workspace-specific `e.g. mmt_aws_usw2_catalog` examples from widget descriptions in `08_genie_ka_mas.py:15` + `09_grant_app_permissions.py:17` and trimmed stale `live glucosphere_dev` + `#68 validation` mentions from `03_compare_baseline_modes.py` widget-context comments.
- **#74 — harness target name isolation via `BUNDLE_VAR_dev_initials` + `BUNDLE_VAR_app_basename`** — two new bundle variables resolve the per-deployer collision risk on harness Apps + `database_instances` (the resource types that bypass the `[dev <USERNAME>]` auto-prefix because brackets aren't DNS-compliant). `dev_initials` (default `user`) appends a personal suffix; `app_basename` (default `glucosphere`) lets operators shorten the base name when long initials push App names past the verified 30-char limit. Applied at 6 hardcoded `name:` sites across the three harness targets. DB instance names allow up to 63 chars (DNS-compliant, verified empirically via API probe), so the constraint is App-side only. `.env.bundle.example` + `DEPLOY.md` variable table updated.
- **Local Python env via `uv`** — new `pyproject.toml` (requires-python>=3.10) + `.python-version` (3.11) + `uv.lock`; added `.venv/` to `.gitignore`. All `python scripts/render_app_yaml.py` invocations across `DEPLOY.md`, `REPO_LAYOUT.md`, `.env.bundle.example`, `scripts/render_app_yaml.py` docstring, and `README.md` updated to `uv run python scripts/...`. `DEPLOY.md` + `README.md` Prerequisites sections explain the one-time `uv sync` setup. Rationale: macOS default `python` = 2.7 → script fails with `SyntaxError: Non-ASCII character`; `uv run` auto-resolves to the project-pinned Python 3.11 without manual venv activation.
- **`DEPLOY.md` step refactor** — removed redundant Step 8 "Run the DLT Pipeline" (the DLT pipeline already runs as the `run_dlt_pipeline` task inside Step 7's `glucosphere_full_setup` job, so manually re-running it was a no-op). Rewrote old Step 9 "Update App Environment Variables" as new Step 8 "Re-render App Environment Variables with Real KA/MAS/Genie IDs" using `render_app_yaml.py`'s `--mas-endpoint` / `--ka-endpoint` / `--genie-space-id` flags (instead of manually editing `app.yaml`). Renumbered old Step 10 → Step 9 (Deploy and Start the App), old Step 11 → Step 10 (Smoke-test). Internal cross-references at DEPLOY.md:9, 251, 257, 374, 417, 467-470 updated to match.
- **README.md + REPO_LAYOUT.md Quick deploy sequences updated** — previously omitted the two-pass deploy (with `render_app_yaml.py` between passes) and the App-start step. New users following just README.md / REPO_LAYOUT.md would NOT have produced a working deploy. Both sequences now reflect the full 7-stage flow + cross-reference `DEPLOY.md` as the canonical step-by-step.
- **`scripts/smoke_test.py`** (NEW) — pre-PR automated smoke test invoked after `bundle run glucosphere_app`. 6 backend checks via Databricks CLI / Statement Execution API (no App SSO auth needed): App state ACTIVE+RUNNING, App URL non-5xx, bundle-managed warehouse exists, gold-table `COUNT(*) > 0`, KA + MAS serving endpoints, Genie space by display-name match. Runtime ~15-30s, exit non-zero on any failure. Catches the same backend failure modes as the manual browser checklist (which now becomes a complementary UI-only verification — DEPLOY.md Step 10 splits "Automated subset" + "Manual browser-driven checks"). Verified against the Phase B redeploy (run `130562462113753`): all 6 checks PASS — `COUNT(*) = 1,982,180` rows in gold; `mas-94acba91-endpoint` + `ka-9d3b46f9-endpoint` + Genie space `01f150850a66184ba68fb1b26f092287` all wired.

### Removed (dead code)

- **`deploy.py`** (395 LOC) — Ward-pixels-pinned Python deploy script flagged in #69. Verified-unused: 0 references in `DEPLOY.md`, no operator runs `python deploy.py` (`DEPLOY.md` documents `databricks bundle deploy` flow exclusively; CHANGELOG.md:203 explicitly says "operators run `bundle run` directly, NOT `python deploy.py`"). Git history preserves.
- **`Data_DataGen_ModelForecast/utils/cleanup_cgm_tables_models.ipynb`** — listed in `Data_DataGen_ModelForecast/README.md` inventory only; not pipeline-wired; had stale `hls_glucosphere.cgm.*` SQL refs throughout.
- **`Data_DataGen_ModelForecast/utils/additional_patient_info/explorations/visualization.py`** — 0 references anywhere; first line declares "This notebook is not executed as part of the pipeline".
- **`TODO.md`** — dev tracking, not user-facing.
- **`App/env.example`** — byte-identical duplicate of `App/.env.example`.

### Moved to gitignored `ref_notes/` (kept locally for future reference)

- **`docs/2026-05-26_synth_e2e_findings.md`** — Phase 1 #68 internal findings doc. `docs/` directory auto-removed (empty after move).
- **`Data_DataGen_ModelForecast/init_lakebase_alerts_schema.py`** — Lakebase #42 setup notebook, not in the current bundle DAG; will be reactivated from `ref_notes/` when #42 resumes.

### Removed (dead config)

- **`Data_DataGen_ModelForecast/configs/baseline_config.yaml`** — 11 dead YAML keys with 0 actual computational uses across the notebook codebase: `glucose_offset`, `alpha_ins`, `alpha_carb`, `alpha_steps`, `alpha_hr`, `alpha_cal`, `carb_mult_lo`, `carb_mult_hi`, `bolus_mult_lo`, `bolus_mult_hi`, `gain_lo`, `gain_hi`. Defined and occasionally printed/logged, but never applied. Pattern suggests carry-over from a deprecated `SyntheticPatient` transformation pipeline. Print statements that referenced them (`04_*:229`, `04_*:1975`, `07_*:181-183`) also removed.

### Notebook content cleanups

- **04 (`pseudo_data_forecast_modeling`)** — dropped two end-of-notebook prose cells (~50 lines): `Pipeline Complete` (redundant with dynamic Pipeline Output Summary above), `Scaling Analysis - Should We Generate More Patients?` (frozen MAE numbers + speculative linear-extrapolation table). Cell 2 (`Production MAE Monitoring Guide`) updated: stripped hardcoded MAE numbers (5.8 / 9.8 / hypo 3.9 / normal 5.4 / hyper 7.3); kept the production-monitoring methodology; added pointer to the dynamic Pipeline Output Summary cell.
- **05 / 06** — dropped `Demo Guide` + `NOTEs` cells (~100 lines each): Demo Guide had hardcoded SQL examples + frozen 30-min-MAE / affected-patient metrics table; NOTEs had internal-team brainstorming about hypo-trending-masked-by-bug scenario. Also dropped: empty cell above Demo Guide, dangling Nature URL cell + `# [optional]` cell after MAE analysis.
- **05 / 06** — model description prose (clean model labels): stripped `(5.8 mg/dL MAE)` / `(10.4 mg/dL MAE)` parentheticals — replaced with `Clean-period XGBoost (15-min / 30-min horizon)`. Plot code (4 `axhline(y=5.8)` reference lines + 12 hypo/hyper threshold lines) UNCHANGED — visual plot output preserved.

### Settled

- **Path 2 (bundle-managed warehouse) verified end-to-end** — 4-pass test on 2026-05-26 confirmed bundle creates `sql_warehouses` resource → `render_app_yaml.py` discovers by name → app.yaml `WAREHOUSE_ID` populated → `09_grant_app_permissions.py` grants `CAN_USE` → app's `/api/sql/query` routes SQL to bundle-managed warehouse. Full write-up in gitignored `ref_notes/2026-05-26_warehouse-bundle-management-verification.md` + reproducible script `ref_notes/2026-05-26_path_2b_test_script.sh`.
- **DABs limitation confirmed (v0.297.2 + v1.0.0)** — `App` resource does NOT expose `service_principal_id` as a bundle-interpolatable property. Fully-declarative path (`sql_warehouses.permissions` referencing App SP) not viable; Option C discover-by-name pattern is the best-practice workaround.
- **`databricks-app` vs `glucosphere-dashboard` naming** — chose `glucosphere-app` to match the `glucosphere-<thing>-${target}` convention used by every other resource (pipeline, job, warehouse, database_instance, harness overrides).

### Fixed (post-eada716 + 4e085e6)

- **`.env.bundle.example` deploy-sequence + `glucosphere-app` rename staleness** (`a013f49`) — workflow section showed `render` BEFORE first deploy, but `render_app_yaml.py` discovers the bundle-managed warehouse by name (which only exists after deploy). Corrected to two-pass: deploy → render → deploy → run. Reference example block had the same wrong sequence. Line 45 `BUNDLE_VAR_app_name=glucosphere-dashboard` → `glucosphere-app`.
- **SSOT silently non-functional — missing `export` prefix on `BUNDLE_VAR_*` lines** — surfaced 2026-05-27 when Phase B kickoff `bundle validate -t mmt_aws_usw2 -o json` returned resolved `catalog = glucosphere_catalog` (the default) instead of the operator's `mmt_aws_usw2`. Root cause: `source .env.bundle` set `BUNDLE_VAR_catalog=mmt_aws_usw2` as a shell-local variable (no `export` prefix), so the `databricks` CLI child process never received it and fell back to `databricks.yml`'s default. Fix: `export` prefix added to all `BUNDLE_VAR_*` lines in `.env.bundle.example` + matching update to `DEPLOY.md:93-95` example. Verified: post-fix `bundle validate` resolves `catalog = mmt_aws_usw2`, `schema = glucosphere_dev` as expected. The Phase A 4-pass verification likely used a different invocation pattern (e.g., pre-exported vars in the test harness) that masked this defect for the committed template.
- **`DOCS_VOLUME` consolidation + `08_genie_ka_mas.py` FUSE bug** — 08 previously used a separate UC Volume `data` (just for the WHO PDF) distinct from the shared `landing_zone` volume that already holds `raw_patient_registry/`, `raw_device_telemetry_stream/`, and `incident_inference_assets/`. Consolidated to `landing_zone/who_docs/`: single UC Volume, single grants surface, less volume-management overhead. Also fixed the same `os.makedirs` → `dbutils.fs.mkdirs` FUSE bug surfaced in 05 (errno 95 EOPNOTSUPP on UC Volume FUSE) — this would have silently broken the WHO PDF copy on a fresh schema (KA endpoint creation would have failed without a knowledge-base file). Doc references in `REPO_LAYOUT.md` + `DEPLOY.md` DAG flow updated to point at the new path.

### Followups (sequenced for next session)

- **Phase B — validation deploy** (~45 min, operator action). Deploy to standalone `mmt_aws_usw2` catalog (NOT `mmt_aws_usw2_catalog`): `source .env.bundle && databricks bundle deploy -t mmt_aws_usw2 && uv run python scripts/render_app_yaml.py --target mmt_aws_usw2 && databricks bundle deploy -t mmt_aws_usw2 && databricks bundle run glucosphere_full_setup -t mmt_aws_usw2`. Verify App `/api/config` returns new catalog/schema and SQL queries route to bundle-managed warehouse.
- **Schema rename** `glucosphere_dev` → `glucosphere` (or `glucosphere_prod`) — operator action after Phase B succeeds. UC supports in-place rename: `databricks schemas update mmt_aws_usw2_catalog.glucosphere_dev --new-name <new> -p fevm-mmt-aws-usw2`.
- **Overview/about-page UI** — separate React commit. First-visit modal (localStorage-flagged) + always-accessible `/about` route explaining Glucosphere-vs-GlucoStream-Intelligence + role-based quick-access cards (clinician / device-support / demo-viewer / developer).

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

  - **Doc extension 2026-05-26** (uncommitted): added a new "Synthetic vs real data — structural realism for incident simulation" section capturing the architectural lesson from the validation iteration log — synthetic distributions are narrow (require curated phenotypes to populate hypo + hyper strata) while real HUPA-UCM provides both tails naturally. Empirically reaffirms the 2026-05-16 default flip to `baseline_source=from_source` AND clarifies why bidirectional incident simulation (#41 — over-reading + under-reading device calibration bugs) needs real-baseline mode specifically. Linked threads: #41 / #72 / #77 / #78. README's "Why `from_source` is the default" para extended to cross-reference the new findings-doc section.

### Fixed

- **Bug 1 — `SCHEMA_NOT_FOUND` in `validate_baseline_source`** (`398d637`). The validate task is the FIRST task in `glucosphere_full_setup` and tried to `CREATE TABLE IF NOT EXISTS baseline_provenance` — but the schema didn't exist yet on fresh-schema deploys (dual_01's `CREATE SCHEMA` runs AFTER dispatch, which is AFTER validate). Latent because live `mmt_aws_usw2.glucosphere_dev` has existed since 2026-05-15. Fix: idempotent `CREATE SCHEMA IF NOT EXISTS` before the table write in `dual_validate_baseline_source.py:107`. Verified via run `891637990308752` validate task: SUCCESS.
- **Bug 2 — Stratified-sampler plan-size assertion fails on synthetic distribution** (fixes `21baa5e` + `df0dc7c` + architectural drop `d377d93`). `dual_04_*.py:109` asserts `actual_plan_size == NUM_PSEUDO` (1000). The original 6 synthetic phenotypes (all means 95-175 mg/dL) produced 0 patients in `hypo_prone` (>15% readings <70) and `mixed` (residual) strata — sampler missing 64 + 1 = 65 patients. Latent because live `from_source` (real HUPA-UCM, 6.59% hypo + diverse profiles) populates all 4 strata naturally.
  - **Iteration 1** (`21baa5e`): added hypo-prone (mean 75, std 20) + brittle T1D (mean 135, std 55) phenotypes → got 999/1000, mixed still empty.
  - **Iteration 2** (`df0dc7c`): tuned brittle (135, 55) → (150, 70) gaussian-targeting mixed — still landed in normal_stable empirically (AR(1) autocorrelation + np.clip(40, 400) inflates time-in-normal above the 60% threshold).
  - **Iteration 3 (architectural pivot)** (`d377d93`): dropped the mixed stratum from sampling targets entirely. mixed was a 0.1% classification residual with no downstream consumer — dashboard doesn't reference it, forecast model training won't notice 0.1% shift. New target ratios: 6.4% hypo / ~71.8% normal (absorbs the 0.1% from mixed) / 21.8% hyper / 0 mixed = 1000 total. Symmetric behavior for synthetic + real_from_source modes; HUPA-UCM still produces N=1000 pseudo-patients with effectively identical composition (1 patient out of 1000 reallocated from mixed-residual to normal_stable). Patient classification (`gen_patient_strata`) keeps all 4 labels for completeness — mixed patients still get classified, just not sampled.

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
