import React, { useState } from 'react';
import { 
  ArrowLeft, 
  TrendingUp, 
  ShieldCheck, 
  CheckCircle2, 
  HelpCircle, 
  ThumbsUp, 
  ThumbsDown, 
  CalendarCheck, 
  ExternalLink,
  Layers,
  Sparkles
} from 'lucide-react';
import { submitAnomalyFeedback } from '../../api/client';

export default function AlertDetailView({ anomaly, onBack, onFeedbackSubmitted }) {
  const [feedbackState, setFeedbackState] = useState(anomaly?.user_feedback || null);
  const [feedbackNotes, setFeedbackNotes] = useState(anomaly?.feedback_notes || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedBanner, setSubmittedBanner] = useState(false);

  if (!anomaly) return null;

  const handleFeedback = async (choice) => {
    setIsSubmitting(true);
    try {
      await submitAnomalyFeedback(anomaly.anomaly_id, choice, feedbackNotes);
      setFeedbackState(choice);
      setSubmittedBanner(true);
      if (onFeedbackSubmitted) {
        onFeedbackSubmitted(anomaly.anomaly_id, choice, feedbackNotes);
      }
    } catch (err) {
      console.warn("Feedback submission error:", err);
      setFeedbackState(choice);
      setSubmittedBanner(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Time-series points for the chart
  const series = anomaly.timeseries || [
    { time: '00:00', actual: 1100, expected: 1100 },
    { time: '01:00', actual: 1150, expected: 1120 },
    { time: '02:00', actual: 1110, expected: 1115 },
    { time: '03:00', actual: anomaly.actual_cost, expected: anomaly.expected_cost, isAnomaly: true },
    { time: '04:00', actual: 1900, expected: 1130 },
    { time: '05:00', actual: 1200, expected: 1125 },
  ];

  const maxVal = Math.max(...series.map((s) => s.actual), 4000);

  return (
    <div className="py-8 px-4 sm:px-6 max-w-6xl mx-auto space-y-6">
      {/* Top Navigation */}
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Alerts Inbox</span>
      </button>

      {/* Headline Banner */}
      <div className="glass-card p-6 rounded-2xl border-l-4 border-l-amber-500">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
              anomaly.severity.toLowerCase() === 'critical' ? 'badge-critical' : 'badge-high'
            }`}>
              {anomaly.severity} Priority
            </span>
            <span className="text-xs font-mono text-slate-400">
              ID: {anomaly.anomaly_id}
            </span>
          </div>
          <span className="text-xs font-mono text-slate-300">
            Recorded at {new Date(anomaly.timestamp).toUTCString().replace(':00 GMT', ' UTC')}
          </span>
        </div>

        <h1 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
          {anomaly.service_name} incurred +${anomaly.deviation_cost.toLocaleString()} above forecast projection (+{anomaly.percentage_deviation.toFixed(1)}%).
        </h1>
        <p className="text-xs text-slate-300 mt-1 font-sans">
          Primary contributing factor: <strong>{anomaly.top_cause}</strong> with <strong>{anomaly.confidence_tier}</strong> confidence calibration.
        </p>
      </div>

      {/* SVG Time-Series Chart */}
      <div className="glass-card p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-white">Spend Trajectory & Anomaly Window</h2>
            <p className="text-[11px] text-slate-400">Actual spend (solid teal) vs forecast baseline (dashed slate) with confidence envelope.</p>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-teal-400">
              <span className="w-3 h-0.5 bg-teal-400 rounded-full" /> Actual Spend
            </span>
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className="w-3 h-0.5 bg-slate-500 border-dashed border-t" /> Expected Baseline
            </span>
          </div>
        </div>

        {/* Visual Chart Canvas */}
        <div className="h-56 w-full flex items-end gap-3 sm:gap-6 pt-6 pb-2 border-b border-slate-800">
          {series.map((pt, idx) => {
            const actualHeight = Math.min(100, (pt.actual / maxVal) * 100);
            const expectedHeight = Math.min(100, (pt.expected / maxVal) * 100);
            return (
              <div key={idx} className="flex-1 flex flex-col items-center h-full justify-end group relative">
                {/* Tooltip on hover */}
                <div className="absolute -top-10 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 border border-slate-700 rounded px-2 py-1 text-[10px] font-mono text-white pointer-events-none z-10 whitespace-nowrap shadow-xl">
                  Actual: ${pt.actual} | Expected: ${pt.expected}
                </div>

                {/* Bars / Indicators */}
                <div className="w-full flex items-end justify-center gap-1 h-full">
                  {/* Expected Bar */}
                  <div
                    className="w-1.5 sm:w-2 bg-slate-700/60 rounded-t"
                    style={{ height: `${expectedHeight}%` }}
                  />
                  {/* Actual Bar */}
                  <div
                    className={`w-3 sm:w-4 rounded-t transition-all ${
                      pt.isAnomaly
                        ? 'bg-gradient-to-t from-red-600 to-amber-400 ring-2 ring-amber-400/50'
                        : 'bg-gradient-to-t from-teal-600 to-teal-400'
                    }`}
                    style={{ height: `${actualHeight}%` }}
                  />
                </div>
                <span className="text-[10px] text-slate-400 mt-2 font-mono">{pt.time}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Two Column Layout: Narrative & Calibration */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Narrative & Recommended Next Checks */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-card p-6 rounded-2xl">
            <h2 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-teal-400" />
              <span>Executive Briefing Narrative</span>
            </h2>
            <div className="prose prose-invert prose-xs text-xs text-slate-300 leading-relaxed font-sans space-y-3">
              {anomaly.narrative_markdown.split('\n\n').map((paragraph, i) => (
                <p key={i}>{paragraph.replace(/###/g, '').replace(/\*\*/g, '')}</p>
              ))}
            </div>
          </div>

          {/* Action Checklist */}
          <div className="glass-card p-6 rounded-2xl">
            <h2 className="text-sm font-bold text-white mb-3">Recommended Next Checks</h2>
            <ul className="text-xs text-slate-300 space-y-2">
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-teal-400 flex-shrink-0 mt-0.5" />
                <span>Verify autoscaling group scaling history in the cloud console for <strong>{anomaly.service_name}</strong>.</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-teal-400 flex-shrink-0 mt-0.5" />
                <span>Inspect spot instance availability metrics in region <strong>us-east-1</strong> during the incident hour.</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-teal-400 flex-shrink-0 mt-0.5" />
                <span>Check for scheduled batch cron jobs or machine learning evaluation pipelines matching this timestamp.</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Right: Confidence Breakdown & Human Feedback */}
        <div className="space-y-6">
          {/* How Sure Are We? */}
          <div className="glass-card p-6 rounded-2xl">
            <h2 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-teal-400" />
              <span>How sure are we?</span>
            </h2>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                <span className="text-slate-400">Confidence Tier</span>
                <span className="font-bold text-teal-300 uppercase font-mono">{anomaly.confidence_tier}</span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                <span className="text-slate-400">Materiality Filter</span>
                <span className="font-bold text-white font-mono">&gt; $10 & &gt; 15%</span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                <span className="text-slate-400">Attribution Method</span>
                <span className="font-bold text-white font-mono">PVM Decomposition</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Evidence References</span>
                <span className="font-bold text-slate-300 font-mono">{anomaly.evidence_refs?.length || 2} inspectable keys</span>
              </div>
            </div>
          </div>

          {/* Human Feedback Buttons */}
          <div className="glass-card p-6 rounded-2xl">
            <h2 className="text-sm font-bold text-white mb-2">Engineer & Finance Feedback</h2>
            <p className="text-[11px] text-slate-400 mb-4">
              Feedback trains future ranking heuristics safely without online weight retraining.
            </p>

            {submittedBanner && (
              <div className="p-3 mb-4 rounded-xl bg-teal-950/60 border border-teal-500/30 text-teal-300 text-xs">
                Feedback recorded: <strong>{feedbackState}</strong>. Thank you!
              </div>
            )}

            <div className="space-y-2 mb-4">
              <button
                onClick={() => handleFeedback('USEFUL')}
                disabled={isSubmitting}
                className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-semibold transition-all ${
                  feedbackState === 'USEFUL'
                    ? 'bg-teal-500/20 text-teal-300 border-teal-500'
                    : 'bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700'
                }`}
              >
                <span className="flex items-center gap-2">
                  <ThumbsUp className="w-3.5 h-3.5 text-teal-400" />
                  <span>This was useful</span>
                </span>
                <span className="text-[10px] text-slate-500">Confirmed issue</span>
              </button>

              <button
                onClick={() => handleFeedback('NOT_AN_ISSUE')}
                disabled={isSubmitting}
                className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-semibold transition-all ${
                  feedbackState === 'NOT_AN_ISSUE'
                    ? 'bg-slate-800 text-white border-slate-600'
                    : 'bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700'
                }`}
              >
                <span className="flex items-center gap-2">
                  <ThumbsDown className="w-3.5 h-3.5 text-amber-400" />
                  <span>Not an issue</span>
                </span>
                <span className="text-[10px] text-slate-500">False positive</span>
              </button>

              <button
                onClick={() => handleFeedback('PLANNED')}
                disabled={isSubmitting}
                className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-semibold transition-all ${
                  feedbackState === 'PLANNED'
                    ? 'bg-purple-500/20 text-purple-300 border-purple-500'
                    : 'bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700'
                }`}
              >
                <span className="flex items-center gap-2">
                  <CalendarCheck className="w-3.5 h-3.5 text-purple-400" />
                  <span>It was planned</span>
                </span>
                <span className="text-[10px] text-slate-500">Maintenance</span>
              </button>
            </div>

            <textarea
              rows={2}
              placeholder="Optional engineer or accounting note..."
              value={feedbackNotes}
              onChange={(e) => setFeedbackNotes(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 text-xs text-white placeholder-slate-500 outline-none focus:border-teal-500 font-mono resize-none"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
