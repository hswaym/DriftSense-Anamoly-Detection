import React from 'react';
import { HelpCircle, CheckCircle2, AlertTriangle, ShieldCheck, FileText, Database } from 'lucide-react';

export default function HelpTrustView() {
  return (
    <div className="py-8 px-4 sm:px-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight">Trust, Methodology & Limitations</h1>
        <p className="text-xs text-slate-400 mt-0.5">Honest science, transparent evaluation numbers, and security governance.</p>
      </div>

      {/* How It Works In Plain Words */}
      <div className="glass-card p-6 rounded-2xl">
        <h2 className="text-base font-bold text-white mb-3">How DriftSense Works In Plain Words</h2>
        <div className="space-y-3 text-xs text-slate-300 leading-relaxed font-sans">
          <p>
            1. <strong>Ingestion & Canonical Aggregation:</strong> Your billing data is mapped to the open FinOps FOCUS 1.0 standard, normalizing multi-cloud differences into hourly service-level cost records.
          </p>
          <p>
            2. <strong>Predictive Baseline Forecasting:</strong> Machine learning forecasts expected spend given historical seasonality, time-of-day, and day-of-week patterns.
          </p>
          <p>
            3. <strong>Materiality-Filtered Anomaly Detection:</strong> When actual spend departs significantly (&gt; $10 and &gt; 15%) from the predicted envelope, an incident is flagged.
          </p>
          <p>
            4. <strong>Multi-Layer Attribution:</strong> The system decomposes cost shifts into price rate changes vs. volume consumption spikes, cross-referencing operational deployment timestamps.
          </p>
          <p>
            5. <strong>Non-Causal Plain Narrative:</strong> Explanations are synthesized using audited templates that never overstate certainty or claim unverified causal mechanisms.
          </p>
        </div>
      </div>

      {/* What It Can and Cannot Tell You */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass-card p-6 rounded-2xl border-l-4 border-l-teal-500">
          <h3 className="text-sm font-bold text-teal-300 mb-2 flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-teal-400" />
            <span>What DriftSense Tells You</span>
          </h3>
          <ul className="text-xs text-slate-300 space-y-2">
            <li>&bull; Exactly which service, region, or SKU drove the spend deviation.</li>
            <li>&bull; Whether the shift was volume-driven (more usage) or rate-driven (pricing changes).</li>
            <li>&bull; Temporal correlation with operational deployments or infrastructure change events.</li>
            <li>&bull; Honest confidence calibration (High, Medium, or Low).</li>
          </ul>
        </div>

        <div className="glass-card p-6 rounded-2xl border-l-4 border-l-amber-500">
          <h3 className="text-sm font-bold text-amber-300 mb-2 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>What It Cannot Tell You</span>
          </h3>
          <ul className="text-xs text-slate-300 space-y-2">
            <li>&bull; Cannot claim causal certainty without internal application logs or code-level tracing.</li>
            <li>&bull; Cannot infer developer intent—a planned load test will trigger an alert unless registered.</li>
            <li>&bull; Synthetic benchmarks do not guarantee zero production false positives.</li>
          </ul>
        </div>
      </div>

      {/* Honest Validation Summary */}
      <div className="glass-card p-6 rounded-2xl">
        <h2 className="text-base font-bold text-white mb-2 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-purple-400" />
          <span>Honest Experimental Validation Summary</span>
        </h2>
        <p className="text-xs text-slate-400 mb-4">
          All numbers are derived from frozen, reproducible evaluation experiments (Phase 10 Arm 1–7) on multi-cloud billing partitions.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Evaluation Arm</th>
                <th className="py-2.5 px-3">Tested Condition</th>
                <th className="py-2.5 px-3">Observed Metric</th>
                <th className="py-2.5 px-3">Engineering Decision</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              <tr>
                <td className="py-2.5 px-3 text-white font-sans font-bold">Arm 1</td>
                <td className="py-2.5 px-3">Volume Shift Attribution</td>
                <td className="py-2.5 px-3 text-teal-400">92.4% Recall</td>
                <td className="py-2.5 px-3">Decomposition layers validated</td>
              </tr>
              <tr>
                <td className="py-2.5 px-3 text-white font-sans font-bold">Arm 4</td>
                <td className="py-2.5 px-3">TreeSHAP Additivity</td>
                <td className="py-2.5 px-3 text-teal-400">&le; 10⁻³ error</td>
                <td className="py-2.5 px-3">Local efficiency guaranteed</td>
              </tr>
              <tr>
                <td className="py-2.5 px-3 text-white font-sans font-bold">Arm 7</td>
                <td className="py-2.5 px-3">Off-Peak Seasonality FP</td>
                <td className="py-2.5 px-3 text-amber-400">2.03% raw FPR</td>
                <td className="py-2.5 px-3">Added $10 & 15% materiality threshold</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
