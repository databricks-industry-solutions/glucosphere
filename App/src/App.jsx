import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import GlucoseLandingDashboard from './pages/GlucoseLandingDashboard'
import CareManagementDashboard from './pages/CareManagementDashboard'
import DiabetesCoachDashboard from './pages/DiabetesCoachDashboard'
import DeviceSupportDashboard from './pages/DeviceSupportDashboard'
import MetricsExplained from './pages/MetricsExplained'
import AboutPage from './pages/AboutPage'
import FirstVisitGate from './components/FirstVisitGate'

function App() {
  return (
    <Router>
      <FirstVisitGate onStartTour={() => window.dispatchEvent(new Event('glucosphere:start-tour'))}>
      <Routes>
        <Route path="/" element={<GlucoseLandingDashboard />} />
        <Route path="/care-management" element={<CareManagementDashboard />} />
        <Route path="/diabetes-coach" element={<DiabetesCoachDashboard />} />
        <Route path="/device-support" element={<DeviceSupportDashboard />} />
        <Route path="/metrics-explained" element={<MetricsExplained />} />
        <Route path="/about" element={<AboutPage />} />
      </Routes>
      </FirstVisitGate>
    </Router>
  )
}

export default App

