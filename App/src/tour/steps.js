// Guided-tour steps keyed to the 90s pitch beats: Detect -> Diagnose -> Assess.
// Each step: the route to be on, a CSS selector to spotlight, and the copy.
export const TOUR_STEPS = [
  { route: '/', selector: '[data-tour="hero-metrics"]', title: '① Detect', body: 'Fleet-wide device accuracy + incident metrics. Drift is flagged the moment it spikes.' },
  { route: '/', selector: '[data-tour="incident-charts"]', title: '① Detect — the signal', body: 'MAE timeline + calibration bias: a direction-agnostic monitor catches over- AND under-reading.' },
  { route: '/device-support', selector: '[data-tour="anomaly-heatmap"]', title: '② Diagnose', body: 'Device error by firmware × day — which firmware drifts, when, and which way (↑ over / ↓ under-read glyphs).' },
  { route: '/diabetes-coach', selector: '[data-tour="coach-risk"]', title: '③ Assess', body: 'See the clinical impact — the selected patient\'s near-term (15/30-min) glucose forecast from the XGBoost model.' },
  // requiresLakebase: GuidedTour filters this out on deploys without the Lakebase binding
  // (the /triage page shows a "not enabled" panel there — nothing to tour).
  { route: '/triage', selector: '[data-tour="triage-queue"]', requiresLakebase: true, title: '→ Act — work the alerts', body: 'The affected cohort lands as a live alert queue (Lakebase-backed Postgres — the app\'s transactional write path): acknowledge · assign · resolve, every action on an audit trail. Don\'t take our word for it — 🛢 Verify in Postgres shows your clicks as database rows.' },
  { route: '/diabetes-coach', selector: '[data-tour="assistant-fab"]', title: 'Ask the assistant', body: 'A built-in AI assistant on every page — device-support troubleshooting + natural-language CGM data queries (Genie).' },
  { route: '/metrics-explained', selector: '[data-tour="metrics-explained"]', title: 'Every metric, explained', body: 'How every number is computed — burden vs fault, MAE, calibration bias, time-in-range — with the SQL behind it.' },
  { route: '/about', selector: '[data-tour="about-hood"]', title: 'Under the hood', body: 'The platform plumbing — Data → ML/AI → Agentic — each node deep-links into the deploying workspace.' },
  // All three variants end on the Roadmap ("The Full Loop") page: the launcher for
  // the three full views + the honest backlog — the natural "explore from here" exit.
  { route: '/full-loop', selector: '[data-tour="roadmap-views"]', title: 'Explore from here', body: 'The three full control-tower views open from these cards — and below them, the honest backlog of what\'s next (streaming, monitoring-created alerts, playback). Done leaves you right here — explore on.' },
];

// Longer "full walkthrough" variant — the same Detect → Diagnose → Assess arc, but
// stopping at every panel worth highlighting (the consolidated heatmap, the drill-in table +
// AI analysis, the firmware chart + per-model drift + ACT, population blast radius, the AI
// assistant). Selected via the tour's Quick/Full chooser; A/B-able by passing { variant: 'full' }.
export const TOUR_STEPS_FULL = [
  { route: '/', selector: '[data-tour="hero-metrics"]', title: '① Detect', body: 'Two headline alerts: High-Risk patients (clinical) and Device-Incident-Affected (the fleet fault). Each links straight to its workflow.' },
  { route: '/', selector: '[data-tour="incident-charts"]', title: '① Detect — the signal', body: 'MAE timeline + calibration bias: a direction-agnostic monitor catches over- AND under-reading device drift.' },
  { route: '/device-support', selector: '[data-tour="anomaly-heatmap"]', title: '② Diagnose — fleet view', body: 'Device error (mean |observed − true|) by firmware × day. FW 4.0 and its 4.0.3 hotfix light up on their incident days (↑ over / ↓ under-read glyphs); 3.14 and 4.1 stay clean.' },
  { route: '/device-support', selector: '[data-tour="out-of-range-table"]', title: 'Drill into any device', body: 'Click a flagged reading for its detail + an AI-powered device analysis (calibration, sensor, firmware, connectivity) from its readings and fleet context.' },
  { route: '/firmware-lifecycle', selector: '[data-tour="firmware-chart"]', title: '② Diagnose — which rollout', body: 'Device error by firmware over time: FW 4.0 and 4.0.3 both spike to ~40 mg/dL on their incident days, clean before (3.14) and after recall (4.1).' },
  { route: '/firmware-lifecycle', selector: '[data-tour="calibration-drift"]', title: '② Diagnose — the device fault', body: 'Per-model calibration drift at its true ±40 mg/dL: Window 1 over-read (Alpha/Gamma on 4.0), Window 2 under-read (Beta/Delta on 4.0.3), 300 devices each. Epsilon/Zeta clean.' },
  { route: '/firmware-lifecycle', selector: '[data-tour="firmware-act"]', title: '→ ACT', body: 'Name the culprit rollouts (4.0 + 4.0.3), size each recall/outreach list, and flag them for rollback — the handoff from diagnosis to action.' },
  { route: '/triage', selector: '[data-tour="triage-queue"]', requiresLakebase: true, title: '→ ACT — the triage queue', body: 'That handoff lands HERE: every affected device as a live alert (Lakebase-backed Postgres). Acknowledge · assign · resolve with outcome menus, fingerstick follow-ups, bulk cohort actions — each writing an audit row, the recall\'s compliance trail. 🛢 Verify in Postgres proves it: copy the query, open the SQL editor (or peek in-page), and see your own actions as rows.' },
  { route: '/population-risk', selector: '[data-tour="pop-risk"]', title: '③ Assess — blast radius', body: "The fault's clinical blast radius: each cohort's device-reported hypo/hyper exposure (top), decomposed below into what the device got right vs the false alarms and missed real events it caused. The roster further down lists who to contact." },
  { route: '/diabetes-coach', selector: '[data-tour="coach-risk"]', title: '③ Assess — per patient', body: 'Down to one patient: their near-term (15/30-min) glucose forecast from the XGBoost model.' },
  { route: '/diabetes-coach', selector: '[data-tour="assistant-fab"]', title: 'Ask the assistant', body: 'A built-in AI assistant — device-support troubleshooting + natural-language CGM data queries (Genie) — available on every page.' },
  // All three variants close on The Full Loop page: it names the arc the tour just
  // walked and hands over the explore-onward cards + the what's-next backlog.
  { route: '/full-loop', selector: '[data-tour="roadmap-views"]', title: 'The full loop', body: 'Detect → Diagnose → Assess — you\'ve just walked the whole loop (on Lakebase deploys, → Act closes it). These cards reopen each view; below them, the honest backlog of what\'s next. Done leaves you right here — explore on.' },
];

// "Interactive" variant — the same Detect → Diagnose → Assess arc as the full walkthrough,
// but the steps that point at LIVE behaviour are flagged `interactive: true`. On those the
// tour card offers "Try it yourself — I'll wait here": the overlay steps aside so the page is
// fully clickable, a floating Resume pill appears, and clicking it returns to the SAME step
// (no restart from step 1). This is the only variant that lets you actually trigger the
// drill-in AI analysis and open the assistant mid-tour. It also adds explicit stops on the
// assistant's engine switch (⚡ Fast ⇄ 🤖 MAS) and the Genie data tab — surfaces that only
// exist while the assistant panel is open, which the interactive FAB step opens.
// Selected via the tour's chooser ({ variant: 'interactive' }). Quick + Full are unchanged.
export const TOUR_STEPS_INTERACTIVE = [
  { route: '/', selector: '[data-tour="hero-metrics"]', title: '① Detect', body: 'Fleet-wide device accuracy + incident metrics. Drift is flagged the moment it spikes.' },
  { route: '/', selector: '[data-tour="incident-charts"]', title: '① Detect — the signal', body: 'MAE timeline + calibration bias: a direction-agnostic monitor catches over- AND under-reading device drift.' },
  { route: '/device-support', selector: '[data-tour="anomaly-heatmap"]', title: '② Diagnose — fleet view', interactive: true, body: 'Device error (mean |observed − true|) by firmware × day. FW 4.0 and its 4.0.3 hotfix light up on their incident days (↑ over / ↓ under-read glyphs); 3.14 and 4.1 stay clean. ▶ Try it: toggle Metric scope In-incident ⇄ Fleet-wide to watch the ~12h fault dilute into a whole-day average.' },
  { route: '/device-support', selector: '[data-tour="out-of-range-table"]', title: 'Drill in — try the AI analysis', interactive: true, body: 'Click any flagged reading to expand its detail, then "Deeper Analysis" for a live AI device report (calibration · sensor · firmware · connectivity — a real 30-60s agent call). Try it; resume when you\'re done.' },
  { route: '/firmware-lifecycle', selector: '[data-tour="firmware-chart"]', title: '② Diagnose — which rollout', body: 'Device error by firmware over time: FW 4.0 and 4.0.3 both spike to ~40 mg/dL on their incident days, clean before (3.14) and after recall (4.1).' },
  { route: '/firmware-lifecycle', selector: '[data-tour="calibration-drift"]', title: '② Diagnose — the device fault', interactive: true, body: 'Per-model calibration drift at its true ±40 mg/dL: Window 1 over-read (Alpha/Gamma on 4.0), Window 2 under-read (Beta/Delta on 4.0.3), 300 devices each. Epsilon/Zeta clean. ▶ Try it: click a faulted model cell to jump to its affected patients on Population Risk.' },
  { route: '/firmware-lifecycle', selector: '[data-tour="firmware-act"]', title: '→ ACT', body: 'Name the culprit rollouts (4.0 + 4.0.3), size each recall/outreach list, and flag them for rollback — the handoff from diagnosis to action.' },
  { route: '/triage', selector: '[data-tour="triage-queue"]', requiresLakebase: true, interactive: true, title: '→ ACT — work the queue', body: 'The live alert queue — every affected patient-device as an actionable alert. ▶ Try it: Ack an alert, expand its row for patient context + audit trail, or filter to FW 4.0 and bulk-resolve the cohort as "🔧 Firmware rolled back". ⟲ Reset demo restores 600 open alerts.' },
  { route: '/triage', selector: '[data-tour="verify-postgres"]', requiresLakebase: true, interactive: true, title: '🛢 Proof: it\'s real Postgres', body: 'The queue is the app\'s ONLY write path — a Lakebase (managed Postgres) OLTP store, not frontend state. ▶ Try it: open 🛢 Verify in Postgres → "Peek right here" — the exact SQL + its live result render under the queue, and the action you just took is a row. Reset demo? That\'s a verifiable TRUNCATE.' },
  { route: '/population-risk', selector: '[data-tour="pop-risk"]', title: '③ Assess — blast radius', interactive: true, body: "The fault's clinical blast radius: each cohort's device-reported hypo/hyper exposure (top), decomposed below into what the device got right vs the false alarms and missed real events it caused. ▶ Try it: switch the matrices' Normalize (per-true-band ⇄ share-of-all); scroll down to the Affected-patient summary and click a region / model bar to filter the roster." },
  { route: '/diabetes-coach', selector: '[data-tour="coach-risk"]', title: '③ Assess — per patient', interactive: true, body: 'Down to one patient: their near-term (15/30-min) glucose forecast from the XGBoost model. ▶ Try it: search {{falseLowId}} — its device displayed a false low (~{{falseLowDisplayed}} mg/dL) while true glucose was actually ~{{falseLowTrue}}; the ⚠ False-low banner warns that treating that fake hypo would push a fine patient HIGH.' },
  // Not interactive: the next two steps auto-open and drive the assistant, so a manual "try it"
  // pause here is redundant friction — this is a plain spotlight → Next.
  { route: '/diabetes-coach', selector: '[data-tour="assistant-fab"]', title: 'Open the assistant', body: "A built-in AI assistant on every page. On the Coach view it opens on the CGM data (Genie) tab — the next two steps show Genie first, then the Fast ⇄ MAS engine switch on the Device-support tab." },
  { route: '/diabetes-coach', selector: '[data-tour="assistant-genie-tab"]', openAssistant: 'genie', title: 'Genie — ask the data', body: 'On the Coach view the assistant opens on "CGM data (Genie)" (the natural default here) — ask the fleet in natural language; Genie writes the SQL and returns the table plus the query it ran.' },
  { route: '/device-support', selector: '[data-tour="assistant-engine"]', openAssistant: 'mas', title: 'Fast ⇄ MAS engine switch', body: "Back on Device-support, the assistant opens on its Device-support tab — toggle the engine: ⚡ Fast (a low-latency router → Genie / Knowledge Assistant / foundation model) — the default — or 🤖 MAS (the Multi-Agent Supervisor), heavier and can be slow. Same question, two orchestration depths." },
  { route: '/metrics-explained', selector: '[data-tour="metrics-explained"]', title: 'Every metric, explained', explore: true, body: 'Each number in the app is defined here — burden vs fault, MAE, calibration bias, time-in-range — with the SQL behind it. Transparency for clinical and device decisions. ▶ Explore: scroll the metric cards and read the SQL behind any number.' },
  { route: '/about', selector: '[data-tour="about-hood"]', title: 'Under the hood', explore: true, body: "The platform plumbing — Data → ML/AI → Agentic — each node deep-links into the deploying workspace (UC, pipeline, jobs, serving endpoints, Genie). ▶ Explore: click any node to open it in the deploying workspace." },
  // All three variants close on The Full Loop page (same rationale as the full tour above).
  { route: '/full-loop', selector: '[data-tour="roadmap-views"]', title: 'The full loop', body: 'Detect → Diagnose → Assess — you\'ve just walked the whole loop (on Lakebase deploys, → Act closes it). These cards reopen each view; below them, the honest backlog of what\'s next. Done leaves you right here — explore on.' },
];
