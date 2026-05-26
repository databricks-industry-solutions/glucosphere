# Synth E2E Validation Findings — 2026-05-26

> **Audience:** glucosphere maintainers (May, Justin, Morgan) + anyone reviewing or extending the synthetic baseline path.
>
> **Status:** Two latent bugs surfaced + fixed. See "Fixes landed" below. Re-validation in flight.

## TL;DR

Phase 1 (#68) E2E validation of the **synthetic baseline path** surfaced **two correctness bugs + one visual-quality bug** that had been masked by the live deploy always running `from_source` (real HUPA-UCM data). All three are now fixed locally on branch `feature/dual-baseline-mmt-aws-usw2`.

| Bug | Where | Why latent | Fix |
|---|---|---|---|
| 1. `SCHEMA_NOT_FOUND` in `validate_baseline_source` | First task of `glucosphere_full_setup` | Live target's `glucosphere_dev` schema pre-existed from prior deploys; fresh sandbox schemas don't | Added `CREATE SCHEMA IF NOT EXISTS` before `CREATE TABLE baseline_provenance` (commit `398d637`) |
| 2. Stratified-sampler plan-size assertion fails | `dual_04_*` line 109 | Plan-size short of `NUM_PSEUDO=1000` (e.g. 935/1000). The diagnostic hint points to `n_available == 0` for one or more strata. Core architectural issue: `mixed` was hardcoded as a sampling TARGET despite being a residual `.otherwise()` classification (not a designed cohort) — AR(1) autocorrelation + clip dynamics make `mixed` effectively unreachable by any synthetic phenotype design. | 3 iterations: added phenotypes (C9), tuned brittle (C12), then **dropped mixed from sampling targets entirely** (C14) — `mixed` was a 0.1% classification residual with no downstream consumer. Allocation absorbed into `normal_stable`. Symmetric behavior across synthetic + real. |

## Context

`#68` is the Phase 1 task in our [2026-05-20 re-locked workflow sequence](#) — validate the synthetic baseline path E2E before merging the dual-baseline cleanup branch to `main`. The synthetic path hadn't been re-validated since 2026-05-15 (24+ commits ago including notebook rename, v9 palette, bidirectional cohort split).

**Setup:** committed two permanent sandbox harness targets to `databricks.yml` (`mmt_aws_usw2_synth_e2e` + `mmt_aws_usw2_from_table_e2e`) using DABs `mode: development`. These auto-prefix resources with `[dev USERNAME]` and isolate from the live `mmt_aws_usw2` target. See `databricks.yml` lines 92-149 for the canonical example.

**Verified along the way (empirical findings worth knowing for any future harness target):**

- `mode: development` auto-prefix applies to **jobs + pipelines only** — NOT to `apps:` or `database_instances:` (DNS-compliance constraints). For those, per-target `resources:` name overrides are needed.
- `${workspace.current_user.short_name}` normalizes dots to underscores in the actual deployed prefix. `may.merkletan` → `[dev may_merkletan]`.
- Databricks App names have a 30-character limit (verified empirically).

## Bug 1: SCHEMA_NOT_FOUND in `validate_baseline_source`

### Symptom

Run `598606749042992` (first synth_e2e deploy) failed immediately at the `validate_baseline_source` task:

```
[SCHEMA_NOT_FOUND] The schema `mmt_aws_usw2_catalog.glucosphere_synth_e2e` cannot be found.
... CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.baseline_provenance (
        baseline_source STRING, source_detail STRING, last_run_at TIMESTAMP)
```

### Root cause

`validate_baseline_source` is the FIRST task in `glucosphere_full_setup` and tries to write a `baseline_provenance` table to the deploy-target's `{catalog}.{schema}`. The schema creation lives in `01_synthetic_baseline.py:18` and `02_ingest_real_baseline.py:75` — but those run AFTER the dispatch task, which runs AFTER validate. So for any **fresh** schema (new workspace, new sandbox target), validate fires before any code has created the schema.

For the live `mmt_aws_usw2` target, `glucosphere_dev` was created on the first deploy back in 2026-05-15 and has persisted ever since. The bug never surfaced there.

### Fix

`Data_DataGen_ModelForecast/utils/validate_baseline_source.py:107` (commit `398d637`):

```python
# Ensure schema exists before writing provenance. dual_01_* notebooks (which
# create the schema themselves) run AFTER this validate task, so for any fresh
# sandbox deploy ... the schema doesn't exist yet at this point. Idempotent
# CREATE SCHEMA IF NOT EXISTS — no-op for existing schemas.
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")
```

The redundant `CREATE SCHEMA` calls in `dual_01_*.py` are left intact — defensive, idempotent, no harm.

### Verified by

Retry run `891637990308752` task `validate_baseline_source`: **SUCCESS**. The fix works.

## Bug 2: Stratified-sampler plan-size assertion fails on synthetic distribution

### Symptom

Retry run `891637990308752` task `datagen_modeling` first attempt (run_id `767146243479756`):

```
AssertionError: [plan-size] expected 1000 pseudo patients in
  mmt_aws_usw2_catalog.glucosphere_synth_e2e.gen_pseudo_plan_7d, got 935.
Per-stratum targets: hypo=64, normal=717, hyper=218, mixed=1 (sum=1000).
"If a stratum was skipped (n_available == 0), the sum will fall short."
```

### Root cause

`04_pseudo_data_modeling.py:422-428` classifies each source patient into one of 4 strata:

| Stratum | Threshold |
|---|---|
| hypo_prone | >15% readings <70 mg/dL |
| hyper_prone | >40% readings >180 mg/dL |
| normal_stable | >60% readings in [70, 180] |
| mixed | else (residual) |

`dual_04:504-507` then HARDCODES per-stratum sample targets to match HUPA-UCM real-distribution ratios (`hypo=64`, `normal=717`, `hyper=218`, `mixed=1` for `NUM_PSEUDO=1000`). The sampler oversamples WITH REPLACEMENT from each stratum's source patients to hit the target.

**The assertion message itself reports only the targets + the diagnostic hint**, not the per-stratum `n_available`. The line that *does* print actual availability (`dual_04:560`: `{stratum}: {target} requested, {n_available} available, returned exactly {target}`) writes to stdout but is not captured in the run artifact retrievable via `databricks jobs get-run-output`. To identify the empty stratum precisely, the Databricks UI cell output is the authoritative source.

**What is structurally provable** (from code + design, independent of which specific stratum was at zero in any given run):

- The classification at `dual_04:424-427` makes `mixed` the `.otherwise()` catch-all — patients who fail *all three* of "hypo_pct>15", "hyper_pct>40", "normal_pct>60". This is a residual category, not a designed cohort.
- AR(1) glucose dynamics + `np.clip(40, 400)` + any phenotype with a single dominant mean tend to produce patients that satisfy ONE of the three thresholds, not none. Iterations C9 + C12 attempted to construct a "brittle T1D" phenotype that would land in `mixed` (~54% normal, just below the 60% threshold) — and empirically still landed in `normal_stable`.
- Therefore: **`mixed` is effectively unreachable by any synthetic phenotype design that uses single-mean AR(1) dynamics.** Hardcoding `target_mixed=1` as a sampling requirement creates an unfillable demand.
- For the live `from_source` path, real HUPA-UCM data naturally covers all 4 strata across its 25 patients with diverse dynamics, so the same hardcoded targets succeed.

### Why was `mixed` even in the datagen — and why dropping it as a sampling target was right

The `mixed` label at `dual_04:427` (`.otherwise("mixed")`) is **legitimately needed as a classification label** — every patient must land somewhere in the partition, and a residual category captures patients who don't satisfy any dominant-range threshold.

The mistake was at `dual_04:504-507` (at commit `398d637`), which **also** used `mixed` as a *sampling target* — `target_mixed = NUM_PSEUDO - target_hypo - target_normal - target_hyper`. This hardcoded the residual quota to mirror HUPA-UCM's accidental proportion (~1 mixed patient out of 25 ≈ 0.1% × 1000 = 1). For synthetic data — where the generator can't produce true mixed-pattern patients by construction — this asks the sampler to find something that doesn't exist.

C14 (`d377d93`) resolved this cleanly by:
- **Keeping `mixed` as a classification label** (every patient still classifies correctly).
- **Dropping `mixed` from the sampling-target list** (sampler no longer requires N mixed patients).
- **Absorbing the freed quota into `normal_stable`** (the closest neighbor; HUPA-UCM's 1 mixed-classified patient still gets included in `gen_patient_strata` for transparency, just not pulled by the sampler).

This is the right structural fix because `mixed` was never a designed cohort — it was a partition artifact. Treating partition artifacts as design targets is the actual bug; the missing-stratum symptom was downstream.

**Why keep the `mixed` label at all (audit / data-quality value):**

The decoupling between *classification* (label every patient) and *sampling* (only pull from designed cohorts) is itself the architectural insight. The `mixed` label is not dead weight — it's an **out-of-band diagnostic signal**:

- **Real-data audit** — HUPA-UCM's ~1 mixed-classified patient is a clinically interesting outlier (atypical glucose pattern: fails dominance threshold in *every* range). Having a label makes them findable in `gen_patient_strata` rather than silently folded into `normal_stable`.
- **Synthetic-data validation** — if synth ever produces N > 0 mixed-classified patients, that's a signal the generator is producing genuinely complex profiles OR accidentally narrow-but-borderline ones. Either way, worth investigating, not hiding.
- **Data-quality regression detection** — a sudden jump in `mixed%` on real data could indicate ingest issues, sensor calibration drift, or a new patient population. Keeping the label preserves that observability for ongoing audits.

**Generalized principle:** classification and sampling can — and often should — have different requirements. Classification serves audit/QC (label everything for traceability). Sampling serves model training (only pull from cohorts the model is designed to learn). Conflating the two — as the pre-C14 code did by hardcoding `target_mixed = NUM_PSEUDO - others` — silently forces unreachable training quotas onto residual partition artifacts.

### Fix

`Data_DataGen_ModelForecast/01_synthetic_baseline.py:52-69` (commit `21baa5e`):

```python
PHENOTYPES = [
    (95,  15, "Type1"),   # well-controlled T1D            → normal_stable
    (140, 30, "Type1"),   # poorly-controlled T1D          → normal_stable/borderline-hyper
    (110, 20, "Type2"),   # well-controlled T2D            → normal_stable
    (160, 40, "Type2"),   # poorly-controlled T2D          → hyper_prone
    (100, 12, "Type1"),   # tight control                  → normal_stable
    (175, 45, "Type2"),   # high baseline                  → hyper_prone
    (75,  20, "Type1"),   # NEW: hypo-prone               → hypo_prone (>15% <70)
    (150, 70, "Type1"),   # NEW: brittle T1D (tuned from initial 135/55 → 150/70 to land in mixed @ ~54% normal, below the 60% normal_stable threshold)
]
```

With `N_PATIENTS=60` cycling through 8 phenotypes, expect 7-8 patients per phenotype. The 7-8 hypo-prone + 7-8 brittle patients should populate the previously-empty strata.

### Validation pending

Re-run synth_e2e after this fix. Read `dual_04`'s "Patient Classification Complete" stratum-counts print (lines 442-448) to verify all 4 strata are non-empty.

### Stats-drift expectation

The 2026-05-16 distribution stats captured in `ref_notes/2026-05-16_dual-baseline-comparison-plots.md` + memory `project_dual_baseline_comparison_results.md` (synthetic mean=134.9, std=34, 0.14% hypo) will shift:

- Hypoglycemia % up (was 0.14% with no hypo-prone phenotype)
- Std up (broader phenotype mix)
- Mean approximately unchanged (new phenotypes balance low + medium)

Will capture new numbers when synth_e2e completes successfully.

## Why both bugs were latent

Both bugs were specific to **fresh-schema** + **synthetic-mode** deploys. Neither condition has held since 2026-05-16 when `baseline_source` default flipped to `from_source` + `glucosphere_dev` was populated. The live deploy has been running in a perpetually-warm state that masked both issues.

Lesson: **harness-based validation against fresh state catches what production-ish testing can't.** This is exactly why the permanent sandbox harness targets (committed in `databricks.yml`) are worth keeping — they exercise the exact code paths customers / fresh-workspace deploys would hit.

## Related context for team

- **Phase 1 #68 finishes when**: synth_e2e validates SUCCESS + from_table_e2e validates SUCCESS. Then phase 2 cleanup → phase 3 merge to main can proceed.
- **Memory of the rename pass**: `real_from_source` → `from_source` and `real_from_table` → `from_table` (mode names now describe mechanism, not data origin). Source-agnostic — `from_table` works on synthetic-populated source too. See CHANGELOG.md 2026-05-26 entry.
- **`from_table_e2e` source is self-bootstrapping**: pulls from `glucosphere_synth_e2e.diabetes_data` (i.e., synth_e2e output). So synth_e2e must succeed before from_table_e2e can run.

## How to retry the validation

```bash
# Synth E2E
databricks bundle deploy -t mmt_aws_usw2_synth_e2e --profile fevm-mmt-aws-usw2
databricks bundle run glucosphere_full_setup -t mmt_aws_usw2_synth_e2e --profile fevm-mmt-aws-usw2 --no-wait

# Watch the stratum classification cell output in dual_04 to confirm
# all 4 strata have non-zero patient counts before the plan-size assertion fires.

# After SUCCESS — from_table E2E (sources from synth output)
databricks bundle deploy -t mmt_aws_usw2_from_table_e2e --profile fevm-mmt-aws-usw2
databricks bundle run glucosphere_full_setup -t mmt_aws_usw2_from_table_e2e --profile fevm-mmt-aws-usw2 --no-wait

# Cleanup both harnesses after validation (bundle destroy doesn't auto-drop UC schemas)
databricks bundle destroy -t mmt_aws_usw2_synth_e2e --auto-approve --profile fevm-mmt-aws-usw2
databricks bundle destroy -t mmt_aws_usw2_from_table_e2e --auto-approve --profile fevm-mmt-aws-usw2
# Then manually DROP SCHEMA glucosphere_synth_e2e + glucosphere_from_table_e2e CASCADE
```

## Bug 3 (visual / quality) — bimodal synthetic distribution

After Bugs 1 + 2 cleared and synth_e2e ran successfully to `datagen_modeling`, the `03_compare_baseline_modes.py` comparison output revealed a **bimodal aggregate glucose distribution** in synthetic baseline (peaks ~100 + ~150 mg/dL, valley ~130). Real HUPA-UCM by contrast is **right-skewed continuous** — see `project_dual_baseline_comparison_results.md` 2026-05-16 numbers (mean 141, median 132, p95 251, single peak).

### Root cause

The 8-phenotype discrete design in `01_synthetic_baseline.py` lines 53-70 (after C9 + C12 additions) had phenotype means clustered into TWO groups:

| Low cluster (~75-110) | High cluster (~140-175) |
|---|---|
| (95, 15) well-controlled T1D | (140, 30) poorly-controlled T1D |
| (110, 20) well-controlled T2D | (160, 40) poorly-controlled T2D |
| (100, 12) tight control | (175, 45) high baseline |
| (75, 20) hypo-prone (C9) | (150, 70) brittle (C12) |

With N=60 patients cycling through 8 phenotypes (7-8 per phenotype) and AR(1) autocorrelation (α=0.97 in dual_01 line 88) keeping each patient's glucose near its phenotype mean, the AGGREGATED histogram inherited the bimodal cluster pattern. No phenotype mean lived in 110-140 → valley.

**This is not a correctness bug** — KPIs/forecast are fine — but is visually unrealistic and would confuse anyone comparing against real CGM population data.

### Fix (C16)

Replaced the discrete `PHENOTYPES` list with continuous per-patient draws:
```python
patient_means = np.clip(np.random.normal(135, 25, N_PATIENTS), 75, 195)
patient_stds  = np.clip(15 + 0.15 * (patient_means - 100) + np.random.normal(0, 3, N_PATIENTS), 10, 60)
```

Per-patient `(mean, std)` continuous → aggregate becomes unimodal right-skewed, matching real HUPA-UCM shape. Stratum coverage in dual_04 still satisfied (some patients have low means → hypo_prone; some high → hyper_prone; majority normal_stable).

Filed originally as task #75 "smooth synthetic distribution" but escalated during harness validation when the bimodal pattern surfaced in the dual_02 comparison plot.

## Architectural pivot 2026-05-26 (resolves the open question below)

The phenotype-tuning path (iterations 1 + 2 above) closed hypo coverage but couldn't reliably populate the `mixed` stratum — AR(1) autocorrelation + np.clip(40, 400) inflate time-in-normal above the 60% normal_stable threshold for any phenotype that doesn't ALSO trigger hypo_prone or hyper_prone. Two empirical attempts confirmed this.

Iteration 3 dropped `mixed` from sampling targets entirely. Rationale:
- `mixed` was a residual classification (`.otherwise("mixed")` in `dual_04` line 427) — not a designed category
- 0.1% allocation (1 patient out of 1000) — numerically negligible for forecast model training
- Dashboard does not reference `mixed` anywhere — KPIs use hypo / hyper / time-in-range
- Real HUPA-UCM had ~1 mixed-classified patient out of 25; that 1 patient is reallocated from mixed-residual sampling to normal_stable. Effectively same cohort composition.

New target ratios: 6.4% hypo / ~71.8% normal / 21.8% hyper / 0 mixed = 1000 total. Symmetric behavior across synthetic + real_from_source / from_table modes. Patient classification (`gen_patient_strata`) keeps all 4 labels for completeness; sampler just doesn't pull from mixed.

## Original open question for team (now resolved)

`dual_04`'s target ratios were HARDCODED to HUPA-UCM proportions including a 0.1% mixed slot. The question was whether to adapt them dynamically or keep hardcoded. **Resolved 2026-05-26 by dropping the mixed slot entirely** — it was a residual classification artifact, not a designed feature. If a future change needs to re-introduce a 4th "mixed-pattern" cohort, design it intentionally rather than recovering it as residual.

A second sub-question — whether `dual_04`'s remaining stratum-ratio targets should adapt to whichever baseline source is in use — was resolved 2026-05-26 by **#77 (commit `6fc74e7`)**: source-adaptive stratum targets that derive ratios from the baseline_source distribution itself (e.g., synth's 0/60/0 hypo/normal/hyper classification feeds a 0%/100%/0% sampling plan; real HUPA-UCM's 6.4%/71.8%/21.8% feeds the matching pseudo plan). Previously hardcoded HUPA-UCM ratios oversampled synth's few hyper patients and caused the pseudo right-shift the user spotted in dual_02 plots.

## Synthetic vs real data — structural realism for incident simulation

Tonight's iterations made it concrete that **synthetic and real data are not interchangeable for this demo's modeling requirements**, and that the 2026-05-16 default flip to `baseline_source=from_source` is the right architectural choice:

### What synthetic naturally produces
- Narrow per-patient (mean, std) distribution — even after C16/C17 widening to `N(125, 35)` + V-shape std envelope, the AR(1) dynamics + `np.clip(40, 400)` inflate time-in-normal so most patients land in the `normal_stable` stratum unless we intentionally construct outlier phenotypes.
- Stratum coverage required iterative phenotype curation — the C9/C12 iterations explicitly added hypo-prone (75, 20) and brittle (135→150, 55→70) phenotypes to ensure hypo + hyper strata had non-zero source patients available to the sampler. A `mixed` patient (the `.otherwise()` residual) was never reachable by any single-mean AR(1) phenotype; C14 dropped it from sampling targets.
- Distribution shape can drift bimodal when generated as a mixture of small-cluster phenotypes (Bug 3 — discrete clusters → bimodal aggregate plot in dual_02). C16 moved to continuous per-patient draws to unify the distribution.
- Lacks naturally-correlated multi-signal extremes (e.g., a hypo event with simultaneously suppressed bolus, elevated heart rate, missed meal) — synthetic signals are independently generated.

### What real HUPA-UCM gives for free
- Natural width: 25 real T1D patients span 6.4% hypo / 71.8% normal / 21.8% hyper without any phenotype curation. The distribution is unimodal right-skewed — matches the shape we have to *engineer* synthetically.
- Sustained hypoglycemic events + hyperglycemic excursions up to ~450 mg/dL, with realistic CGM signal noise from FreeStyle Libre 2 sensor characteristics.
- Naturally-correlated multi-signal extremes — when a real patient went hypo, their behavioral signals correlated in clinically plausible ways.

### Why this matters for incident simulation (esp. bidirectional)
The platform's incident simulation overlays **device calibration bugs** on top of the baseline glucose stream (see `05_incident_inference_bidirectional.py`). A meaningful bidirectional bug demo (over-reading AND under-reading sensor drift, per [[reference-bidirectional-cgm-calibration-bugs]]) requires baseline data with **both tails** populated:

- **Over-reading bug (+40 mg/dL) on a hypo-prone patient** — sensor masks a real hypoglycemic event; patient sees "normal" reading while actually crashing. Clinically high-risk. Requires baseline data with hypo events to surface this.
- **Under-reading bug (-40 mg/dL) on a hyper-prone patient** — sensor masks a real hyperglycemic excursion; patient may over-bolus or fail to act. Requires baseline data with sustained hyperglycemia.

Synthetic-only baselines must artificially construct each clinically-meaningful stratum via phenotype curation. The validation iterations documented above (Bug 2 stratum coverage; Bug 3 distribution shape) demonstrate that this construction is brittle — minor changes to phenotype parameters can collapse a stratum, introduce bimodal artifacts, or fail to populate residual classifications like `mixed`. Real-baseline gives all designed strata empirically + naturally across its 25 source patients, which is exactly the substrate the bidirectional bug demo (#41) needs.

### Synthetic-vs-real design philosophy (architectural framing)

Two valid framings, both reflected in the current code:

1. **"Synthetic is a textbook idealization."** Synthetic represents a curated "well-managed diabetes" cohort intended for CI / smoke tests / restricted-egress environments where Mendeley network access isn't available. Differences from real are accepted features, not bugs. This framing is preserved in README's "Why `from_source` is the default" paragraph.
2. **"Synthetic should populate the same strata real does."** For the harness pipeline to work end-to-end across both baseline modes without code branches, synthetic MUST produce hypo + hyper + normal patients in proportions the sampler can consume. This framing drove the C9 → C18 iteration chain — explicit phenotype curation (C9/C12), continuous draws (C16), distribution widening (C17), and source-adaptive stratum ratios (C18/#77).

**The current code lands at a hybrid:** synthetic produces all *sampled* strata with reasonable per-stratum representation, matching the sampler's structural needs. Synthetic still differs from real in tail width, multi-signal correlations, and the natural occurrence of edge cases like the `mixed` residual classification — those gaps are accepted as the cost of in-cluster deterministic generation without external data.

**Stronger framing #2 (full real-emulation) would require:** modeling correlated multi-signal dynamics (e.g., a hypo event simultaneously suppressing bolus + elevating heart rate + missing meals), reproducing the long-tail outliers HUPA-UCM exhibits (sustained excursions to ~450 mg/dL), and engineering enough phenotype variety that the residual `mixed` classification naturally populates without being engineered. None of those are blockers for today's harness validation; they're separate research investments if/when the synthetic path needs to stand alone for richer demos.

### Consequence for default + future demos
- **Default stays `from_source`** — empirically validated by the iteration log above. Synthetic remains valid for CI / restricted-egress / smoke-test scenarios where a known well-behaved fixture is preferred.
- **Bidirectional bug demo (#41)** should run against `from_source` data exclusively. Synthetic baselines would under-stress at least one direction of the bug.
- **Harness validation matrix should always include `from_source`** — synth-only validation will miss distribution-width regressions that real data catches naturally (as Bug 2 latently demonstrated for two weeks against the live target before #68 surfaced it).
- **Future synthetic improvements** should be measured against real HUPA-UCM as the reference shape (`03_compare_baseline_modes.py` is the working tool for this). If a synthetic-only KS-test deviation exceeds a threshold, treat it as a regression.

### Linked architectural threads
- **#41 bidirectional CGM calibration bugs** — uses this real-baseline substrate.
- **#72 from_table source auto-detect** — priority `glucosphere_dev` (live, real) → `glucosphere_from_source_e2e` (real harness) → `glucosphere_synth_e2e` (synth harness) encodes the same preference for real data when both exist.
- **#77 source-adaptive stratum ratios** — propagates the source's natural distribution into the pseudo-patient sampler, instead of forcing real-data ratios onto a synth source.
- **#78 endpoint name collision** (parking-lot) — surfaced when running 3 harnesses concurrently against a shared workspace; harness pattern needs schema-namespaced endpoint names to support multi-mode regression validation in parallel.
