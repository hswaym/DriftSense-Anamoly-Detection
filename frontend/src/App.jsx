import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import DemoBanner from './components/DemoBanner';
import WelcomeView from './components/screens/WelcomeView';
import UploadWizard from './components/screens/UploadWizard';
import OverviewView from './components/screens/OverviewView';
import AlertsInboxView from './components/screens/AlertsInboxView';
import AlertDetailView from './components/screens/AlertDetailView';
import ExploreView from './components/screens/ExploreView';
import ReportsView from './components/screens/ReportsView';
import SettingsView from './components/screens/SettingsView';
import ExpertDrawer from './components/screens/ExpertDrawer';
import HelpTrustView from './components/screens/HelpTrustView';

import { SAMPLE_ANALYSIS, SAMPLE_ANOMALIES } from './data/sampleDataset';
import { getAnalysisOverview, listAnomalies } from './api/client';

export default function App() {
  const [activeScreen, setActiveScreen] = useState('welcome');
  const [isDemoMode, setIsDemoMode] = useState(true);
  const [showExpert, setShowExpert] = useState(false);
  const [tenantId, setTenantId] = useState('tenant_demo');

  // Active analysis & anomalies data
  const [analysis, setAnalysis] = useState(SAMPLE_ANALYSIS);
  const [anomalies, setAnomalies] = useState(SAMPLE_ANOMALIES);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState(SAMPLE_ANOMALIES[0].anomaly_id);

  // Sync with API when analysis ID changes (if not demo mode)
  const loadAnalysisData = async (analysisId) => {
    try {
      const [overview, anomList] = await Promise.all([
        getAnalysisOverview(analysisId, tenantId),
        listAnomalies(analysisId, null, null, tenantId),
      ]);
      setAnalysis(overview);
      if (anomList && anomList.length > 0) {
        setAnomalies(anomList);
        setSelectedAnomalyId(anomList[0].anomaly_id);
      }
    } catch (err) {
      console.warn("Unable to fetch live API data, retaining current data:", err);
    }
  };

  const handleTryDemo = () => {
    setIsDemoMode(true);
    setAnalysis(SAMPLE_ANALYSIS);
    setAnomalies(SAMPLE_ANOMALIES);
    setSelectedAnomalyId(SAMPLE_ANOMALIES[0].anomaly_id);
    setActiveScreen('overview');
  };

  const handleUploadClick = () => {
    setActiveScreen('upload');
  };

  const handleAnalysisCompleted = (analysisId) => {
    setIsDemoMode(false);
    loadAnalysisData(analysisId);
    setActiveScreen('overview');
  };

  const handleSelectAnomaly = (anomalyId) => {
    setSelectedAnomalyId(anomalyId);
    setActiveScreen('detail');
  };

  const handleFeedbackSubmitted = (anomalyId, feedback, notes) => {
    setAnomalies((prev) =>
      prev.map((a) =>
        a.anomaly_id === anomalyId
          ? { ...a, user_feedback: feedback, feedback_notes: notes, status: feedback === 'PLANNED' ? 'Resolved' : 'Investigating' }
          : a
      )
    );
  };

  const currentAnomaly = anomalies.find((a) => a.anomaly_id === selectedAnomalyId) || anomalies[0];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Demo Banner */}
      <DemoBanner
        isDemoMode={isDemoMode}
        setIsDemoMode={setIsDemoMode}
        onUploadClick={handleUploadClick}
      />

      {/* Main Navbar */}
      <Navbar
        activeScreen={activeScreen}
        setActiveScreen={setActiveScreen}
        isDemoMode={isDemoMode}
        setIsDemoMode={setIsDemoMode}
        showExpert={showExpert}
        setShowExpert={setShowExpert}
      />

      {/* Active Screen View */}
      <main className="flex-1 pb-16">
        {activeScreen === 'welcome' && (
          <WelcomeView onTryDemo={handleTryDemo} onUploadClick={handleUploadClick} />
        )}
        {activeScreen === 'upload' && (
          <UploadWizard
            onAnalysisCompleted={handleAnalysisCompleted}
            onCancel={() => setActiveScreen('overview')}
          />
        )}
        {activeScreen === 'overview' && (
          <OverviewView
            analysis={analysis}
            anomalies={anomalies}
            onSelectAnomaly={handleSelectAnomaly}
            onGoToInbox={() => setActiveScreen('inbox')}
          />
        )}
        {activeScreen === 'inbox' && (
          <AlertsInboxView
            anomalies={anomalies}
            onSelectAnomaly={handleSelectAnomaly}
          />
        )}
        {activeScreen === 'detail' && (
          <AlertDetailView
            anomaly={currentAnomaly}
            onBack={() => setActiveScreen('inbox')}
            onFeedbackSubmitted={handleFeedbackSubmitted}
          />
        )}
        {activeScreen === 'explore' && (
          <ExploreView analysis={analysis} />
        )}
        {activeScreen === 'reports' && (
          <ReportsView
            analysisId={analysis?.analysis_id || 'anl_sample_prod_01'}
            tenantId={tenantId}
          />
        )}
        {activeScreen === 'settings' && (
          <SettingsView
            tenantId={tenantId}
            setTenantId={setTenantId}
          />
        )}
        {activeScreen === 'trust' && (
          <HelpTrustView />
        )}
      </main>

      {/* Slide-out Expert Details Drawer */}
      <ExpertDrawer
        isOpen={showExpert}
        onClose={() => setShowExpert(false)}
        selectedAnomaly={currentAnomaly}
      />

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 text-center text-xs text-slate-500 font-mono">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>DriftSense Enterprise v2.0 &bull; FOCUS 1.0 Aligned</span>
          <span>Non-Causal Language Guard Active &bull; Zero Untracked Hallucination</span>
        </div>
      </footer>
    </div>
  );
}
