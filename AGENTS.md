# AGENTS.md — operating principles for this repo

Guidance for AI coding agents (and humans) working in Glucosphere. This complements
`CONTRIBUTING.md` (human workflow) and the per-area `README.md` files. It captures
project-specific principles that are easy to get wrong and expensive to discover late.

> Tool-general Databricks-notebook editing gotchas (e.g. `%run` must be the only content
> of its cell; notebook cell edits are position-fragile) are **not** repo-specific — keep
> those in a reusable agent skill, not here. This file is for **Glucosphere** facts.

## 1. Data-gen is the source of truth — make synthetic attributes deterministic

Per-patient synthetic attributes must be a **deterministic function of `patient_id`**, not
a random draw, a positional zip onto a non-deterministic Spark order, or a seed that only
holds within one notebook. Otherwise the same patient gets different values across runs and
across the notebooks that each "invent" the attribute, and the demo's story silently breaks
on a fresh deploy.

- `device_model` is `md5(patient_id)` → weighted bucket, defined **once** in
  `Data_DataGen_ModelForecast/utils/additional_patient_info/_device_model_spec.py` and
  `%run`-shared by the incident simulation (`05`), the patient registry, and the device
  telemetry generator — so all three carry the identical value with no read-ordering
  dependency and **no random fallback**.
- The calibration-bias cohorts (over-read `Alpha/Gamma`, under-read `Beta/Delta`, clean
  `Epsilon/Zeta`) follow from that deterministic `device_model`.
- If you add a new synthetic attribute, follow the same pattern (derive from `patient_id`,
  define once, share). Do not reach for `np.random.choice` zipped to `distinct().toPandas()`.

## 2. Enforce data invariants in the sanity gate, not by inspection

`Data_DataGen_ModelForecast/utils/data_sanity_checks.py` runs after the pipeline and
**fails the job** on clinically-impossible or story-breaking data (glucose outside the CGM
range, implausible diagnosis-by-age, a clean device model appearing in an incident cohort,
etc.). When you add a load-bearing invariant, add a check here so a regression breaks the
run loudly instead of shipping silently.

## 3. Fix data issues at the source; a column's definition must match its docs

A derived column is consumed by many panels. Fix the **definition** once rather than
patching each consumer. And a metric must mean what its documentation says — e.g.
`glucose_out_of_range` is *purely* `glucose < 70 OR glucose > 180` (matching the Genie /
Metrics-Explained docs); it must not fold in unrelated state like incident membership,
which would inflate every out-of-range panel.

## 4. A visualization that doesn't "pop" is an app/query fix — never a data mutation

If a chart reads muddy, change the **query or the panel**, not the shared pipeline data.
Never re-run the pipeline against the shared schema to make a visual look better — that
rewrites the dataset every other view reads. Pick the metric that actually carries the
signal (e.g. device-error / calibration drift reads cleanly where a whole-window
out-of-range *rate* is diluted by the real-data baseline).

## 5. Validate on a sandbox, never the frozen demo

Data-gen changes take effect on a pipeline re-run. Run them against an **isolated sandbox**
catalog/schema (the `*_e2e` harness targets), never the live/frozen demo schema. Verify the
result (query the gold tables, check the sanity gate passed) before declaring success.

## 6. App deploy hygiene — pin the app name; render before deploy

The Databricks App resource is named `${var.app_name}`. **Always pass the same
`BUNDLE_VAR_app_name` on every deploy** — deploying with a different (or default) name
renames/recreates the app resource, which tears down its endpoint (DNS) and service
principal grants. Render `app.yaml` for the target *before* `bundle deploy`, deploy + run
the app, then revert the rendered `app.yaml` (it carries generic placeholders in git).
Because that revert restores **blank** ids, you must **re-render before *every* deploy**, not
just the first — render-with-nothing ships blanks (dashboards point at the placeholder
catalog, the assistant/Genie tabs go empty). Warehouse / job / pipeline / forecast
auto-discover by deterministic name; `catalog`/`schema` come from `BUNDLE_VAR_*`; but the
**KA/MAS/Genie hex ids are not discoverable** — supply them via `--mas-endpoint` /
`--ka-endpoint` / `--genie-space-id` flags **or** capture them once into
`.env.bundle.<target>` as `BUNDLE_VAR_mas_endpoint` / `BUNDLE_VAR_ka_endpoint` /
`BUNDLE_VAR_genie_space_id` so each re-render is flag-free (see DEPLOY.md → *Re-deploying
after a code or frontend change*). New App service principals need UC + warehouse + endpoint
grants (`scripts/grant_app_sp.py`).

Keep **workspace-specific coords out of committed files**: catalog / schema / profile /
app name / warehouse id belong only in the gitignored `.env.bundle.<target>` (the single
source of truth), never hardcoded in `databricks.yml` target stanzas **or their comments**,
nor in committed `app.yaml`. The committed `databricks.yml` and `app.yaml` carry generic
placeholders so the public repo never leaks a real workspace — describe a target by the
*mechanism* (env-driven, reuse-vs-create-own) in comments, not by its literal values.

## 7. Clinical honesty

Report **rates, not raw counts** (a model with more patients isn't "worse" for having more
readings). Remember the real CGM baseline: people with diabetes sit out-of-range ~⅓ of the
time, so a transient device fault is invisible in a whole-window OOR rate — surface it with
a direct device-error view instead. Keep clinical thresholds data-agnostic and honest.

## 8. Leave it better — and keep this file living (the campsite rule)

Leave every artifact you touch a little better than you found it: a stale comment, a broken
link, a misleading doc, a redundant query you noticed while doing something else — fix it in
the same pass, don't file it for "later." That applies to code, config, docs, and assets.

This file (and the per-area READMEs, and any reusable agent skills) is **living** — when you
learn a new gotcha or land an improvement worth remembering, **add it here** so the next
contributor (agent or human) inherits it instead of rediscovering it the hard way. A lesson
that only lives in one person's head or one session's memory will be re-learned expensively.
Project-specific lessons → this file; reusable tool-general lessons → the relevant skill.

## 9. Distrust "it's always worked" — consolidated legacy code harbors latent bugs

This repo was assembled from buildathon assets plus later cleanups. Code that has "always
worked" can carry **latent bugs that only surface under new conditions** — they survived
because nothing previously exercised the edge, not because they're correct.

Worked example (2026-06-02): the gold reading→firmware join in `transformations.sql` used an
**inclusive** `time BETWEEN start_time AND end_time`. Each firmware interval's `end_time`
equals the next interval's `start_time`, so a reading at the exact transition instant matched
*both* intervals and was duplicated. Latent since the buildathon (commit `d0bcf7c`,
2026-01-29) — only ~0.15% of rows, so no metric visibly moved — until a 4th firmware version
(one more transition) **and** a new cohort sanity check made it structurally visible at the
incident boundary. Fix: half-open `>= start AND < end`.

So:
- When a sanity gate fires on "old, untouched" code, treat it as a **real find**, not a false
  positive. `git log -S '<snippet>'` / blame to see how old it is — "it's legacy" is a reason
  to fix it, not to excuse it.
- Any change that adds a **new case** (an extra enum value, era, join key, cohort) is exactly
  the new condition that wakes a latent bug — expect it, and re-validate row counts and joins
  (e.g. `GROUP BY key HAVING COUNT(*) > 1` to catch fan-out) after the change.
- Fix at the source so every consumer benefits, then grep for the same anti-pattern elsewhere
  (e.g. other inclusive interval joins) — fix the **class**, not just the instance.

## 10. Lakebase (alert-triage OLTP) — what bites, in order

The triage queue's Postgres lives OUTSIDE the bundle; the bundle only carries the App's
`postgres` resource binding (referencing `projects/<id>/branches/production` by name).
Hard-won rules (all from the 2026-06-12 destroy→rebuild incident — see
`lakebase_probe/README.md` and DEPLOY.md → *Lakebase one-time setup* / *Teardown*):

- **Never bundle-manage a stateful DB.** `bundle destroy` deletes the project INCLUDING
  data, and Lakebase deletion is soft — the id stays tombstoned (~7 days), so a same-id
  recreate fails "already exists". The bind/import path can't repair it either: the
  provider never reads back `spec`, so a bound project perpetually re-plans as `recreate`.
  External `databricks postgres create-project` once; the binding re-attaches by name.
- **app.yaml's `resources:` section is INERT** — app deploys don't apply it. The binding
  must live on the bundle App resource (databricks.yml). `render_app_yaml.py` renders only
  the `LAKEBASE_ENDPOINT` env var.
- **Every App recreate rotates its service principal**, and the rotated SP does not own
  the PG objects its predecessor created. `App/databricks/lakebase.py` is rotation-proofed
  three ways (PUBLIC read/write grants; probe-first bootstrap — re-running DDL as a
  non-owner fails on `CREATE INDEX`'s ownership check; `TRUNCATE` without
  `RESTART IDENTITY` — sequence restart needs ownership). Don't "simplify" those away.
- **No grant scripts for Lakebase** — the binding auto-creates the SP's PG role; the app
  bootstraps + owns its `triage` schema at first touch. If a rotated SP is still denied
  (pre-rotation-proofing schema), the operator fix is control-plane, not SQL:
  `databricks postgres delete-role` on the ORPHANED old-SP role reassigns its objects to
  the project owner (SQL can't — `databricks_superuser` membership is granted without
  the SET option).
- **Trust smoke check 9, not "binding present".** The functional `/api/alerts` probe is
  the only layer that catches app↔schema permission breaks — project+binding checks
  passed while every queue call 500'd.
