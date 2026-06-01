// Guided-tour steps keyed to the 90s pitch beats: Detect -> Diagnose -> Assess.
// Each step: the route to be on, a CSS selector to spotlight, and the copy.
export const TOUR_STEPS = [
  { route: '/', selector: '[data-tour="hero-metrics"]', title: '① Detect', body: 'Fleet-wide device accuracy + incident metrics. Drift is flagged the moment it spikes.' },
  { route: '/', selector: '[data-tour="incident-charts"]', title: '① Detect — the signal', body: 'MAE timeline + calibration bias: a direction-agnostic monitor catches over- AND under-reading.' },
  { route: '/device-support', selector: '[data-tour="anomaly-heatmap"]', title: '② Diagnose', body: 'Trace the spike to the device model × firmware version at fault.' },
  { route: '/diabetes-coach', selector: '[data-tour="coach-risk"]', title: '③ Assess', body: 'See the clinical impact — the selected patient\'s near-term (15/30-min) glucose forecast from the XGBoost model.' },
];

// Longer "full walkthrough" variant — the same Detect → Diagnose → Assess arc, but
// stopping at every panel worth highlighting (drift, the drill-in table + AI analysis,
// firmware ACT, population blast radius, the AI assistant). Selected via the tour's
// Quick/Full chooser; A/B-able by passing { variant: 'full' } to the start event.
export const TOUR_STEPS_FULL = [
  { route: '/', selector: '[data-tour="hero-metrics"]', title: '① Detect', body: 'Two headline alerts: High-Risk patients (clinical) and Device-Incident-Affected (the fleet fault). Each links straight to its workflow.' },
  { route: '/', selector: '[data-tour="incident-charts"]', title: '① Detect — the signal', body: 'MAE timeline + calibration bias: a direction-agnostic monitor catches over- AND under-reading device drift.' },
  { route: '/device-support', selector: '[data-tour="anomaly-heatmap"]', title: '② Diagnose — fleet view', body: 'Out-of-range rate by device model × firmware. Firmware 4.0 is the hot column.' },
  { route: '/device-support', selector: '[data-tour="calibration-drift"]', title: '② Diagnose — the device fault', body: 'Calibration drift isolates the fault at its true ±40 mg/dL: Window 1 over-read, Window 2 under-read, 300 devices each. Epsilon/Zeta stay clean.' },
  { route: '/device-support', selector: '[data-tour="out-of-range-table"]', title: 'Drill into any device', body: 'Click a flagged reading for its detail + an AI-powered device analysis (calibration, sensor, firmware, connectivity) from its readings and fleet context.' },
  { route: '/firmware-lifecycle', selector: '[data-tour="firmware-chart"]', title: '② Diagnose — which rollout', body: 'Device error by firmware over time: FW 4.0 spikes to ~40 mg/dL during the incident, clean before (3.14) and after recall (4.1).' },
  { route: '/firmware-lifecycle', selector: '[data-tour="firmware-act"]', title: '→ ACT', body: 'Name the culprit rollout, size the recall/outreach list, and flag it for rollback — the handoff from diagnosis to action.' },
  { route: '/population-risk', selector: '[data-tour="pop-risk"]', title: '③ Assess — blast radius', body: 'The clinical impact of the fault across the affected cohort — who to contact, by region and device model.' },
  { route: '/diabetes-coach', selector: '[data-tour="coach-risk"]', title: '③ Assess — per patient', body: 'Down to one patient: their near-term (15/30-min) glucose forecast from the XGBoost model.' },
  { route: '/diabetes-coach', selector: '[data-tour="assistant-fab"]', title: 'Ask the assistant', body: 'A built-in AI assistant — device-support troubleshooting + natural-language CGM data queries (Genie) — available on every page.' },
];
