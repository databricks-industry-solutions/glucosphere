import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import GlucoseLandingDashboard from './pages/GlucoseLandingDashboard'
import CareManagementDashboard from './pages/CareManagementDashboard'
import DiabetesCoachDashboard from './pages/DiabetesCoachDashboard'
import DeviceSupportDashboard from './pages/DeviceSupportDashboard'
import MetricsExplained from './pages/MetricsExplained'
import AboutPage from './pages/AboutPage'
import RoadmapPage from './pages/RoadmapPage'
import FirmwareLifecyclePage from './pages/FirmwareLifecyclePage'
import PopulationRiskPage from './pages/PopulationRiskPage'
import TriagePage from './pages/TriagePage'
import FirstVisitGate from './components/FirstVisitGate'
import GuidedTour from './components/GuidedTour'
import AppShell from './components/AppShell'

function App() {
  return (
    <Router>
      <FirstVisitGate onStartTour={() => window.dispatchEvent(new Event('glucosphere:start-tour'))}>
      <AppShell>
      <Routes>
        <Route path="/" element={<GlucoseLandingDashboard />} />
        <Route path="/care-management" element={<CareManagementDashboard />} />
        <Route path="/diabetes-coach" element={<DiabetesCoachDashboard />} />
        <Route path="/device-support" element={<DeviceSupportDashboard />} />
        <Route path="/metrics-explained" element={<MetricsExplained />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/full-loop" element={<RoadmapPage />} />
        {/* Legacy alias: the page lived at /roadmap until the 2026-06-12 "The Full
            Loop" rename — keep old bookmarks/shared links working via redirect. */}
        <Route path="/roadmap" element={<Navigate to="/full-loop" replace />} />
        <Route path="/firmware-lifecycle" element={<FirmwareLifecyclePage />} />
        <Route path="/population-risk" element={<PopulationRiskPage />} />
        {/* Alert Triage (Lakebase-backed) — route always registered; the page itself
            shows a "not enabled" panel when the target lacks the Lakebase binding,
            and nothing links here in that case (links are flag-gated). */}
        <Route path="/triage" element={<TriagePage />} />
      </Routes>
      </AppShell>
      </FirstVisitGate>
      <GuidedTour />
    </Router>
  )
}

export default App

