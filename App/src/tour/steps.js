// Guided-tour steps keyed to the 90s pitch beats: Detect -> Diagnose -> Assess.
// Each step: the route to be on, a CSS selector to spotlight, and the copy.
export const TOUR_STEPS = [
  { route: '/', selector: '[data-tour="hero-metrics"]', title: '① Detect', body: 'Fleet-wide device accuracy + incident metrics. Drift is flagged the moment it spikes.' },
  { route: '/', selector: '[data-tour="incident-charts"]', title: '① Detect — the signal', body: 'MAE timeline + calibration bias: a direction-agnostic monitor catches over- AND under-reading.' },
  { route: '/device-support', selector: '[data-tour="anomaly-heatmap"]', title: '② Diagnose', body: 'Trace the spike to the device model × firmware version at fault.' },
  { route: '/diabetes-coach', selector: '[data-tour="coach-risk"]', title: '③ Assess', body: 'See the clinical impact — patient risk windows for the affected cohorts.' },
];
