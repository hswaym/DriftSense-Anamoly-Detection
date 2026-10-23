import React from 'react';
import { X, SlidersHorizontal, Hash, Cpu, BarChart, ShieldCheck } from 'lucide-react';

export default function ExpertDrawer({ isOpen, onClose, selectedAnomaly }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/70 backdrop-blur-sm flex justify-end">
      <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full p-6 overflow-y-auto space-y-6 shadow-2xl">
        {/* Drawer Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2 text-purple-400">
            <SlidersHorizontal className="w-5 h-5" />
            <h2 className="text-base font-bold text-white">Expert Science & SHAP Drawer</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* TreeSHAP Feature Contributions Waterfall */}
        <div className="glass-card p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-teal-400" />
              <span>Local TreeSHAP Waterfall Values</span>
            </h3>
            <span className="text-[10px] font-mono text-teal-400">atol &le; 1e-3 additivity</span>
          </div>
          <p className="text-[11px] text-slate-400 mb-4">
            Marginal Shapley contribution to the residual prediction for {selectedAnomaly?.service_name || 'AmazonEC2'}.
          </p>

          <div className="space-y-3 font-mono text-xs">
            {(selectedAnomaly?.shap_contributions || [
              { feature: "usage_quantity_surge", value: "+$1,940.00", pct: 71.3 },
              { feature: "on_demand_rate_mix", value: "+$520.00", pct: 19.1 },
              { feature: "cross_az_traffic", value: "+$260.00", pct: 9.6 },
            ]).map((s, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-300 font-sans">{s.feature}</span>
                  <span className="text-teal-400 font-bold">{s.value} ({s.pct}%)</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-teal-500 to-teal-400"
                    style={{ width: `${s.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Residual Error & Variance Envelopes */}
        <div className="glass-card p-5 rounded-2xl">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <BarChart className="w-4 h-4 text-indigo-400" />
            <span>Residual Noise & Arm 7 Variance Audit</span>
          </h3>
          <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
            Off-peak/weekend hours experience low-baseline variance collapse ($2 micro-shifts triggering statistical 3&sigma; alerts), justifying our $10 & 15% materiality threshold.
          </p>
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-1.5 font-mono text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-400">Clean FPR (Peak Hours):</span>
              <span className="text-teal-400">0.07%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Clean FPR (Weekend Off-Peak):</span>
              <span className="text-amber-400">2.03% (filtered by materiality)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Net Production False Alarm Rate:</span>
              <span className="text-teal-300 font-bold">&le; 0.45%</span>
            </div>
          </div>
        </div>

        {/* Cryptographic Manifest Hashes */}
        <div className="glass-card p-5 rounded-2xl">
          <div className="flex items-center gap-1.5 mb-2 text-white text-xs font-bold uppercase tracking-wider">
            <Hash className="w-4 h-4 text-purple-400" />
            <span>Frozen Reproducibility Hashes</span>
          </div>
          <p className="text-[11px] text-slate-400 mb-3">
            Cryptographic SHA-256 fingerprint verified against Colab notebook executions.
          </p>

          <div className="space-y-2 text-[10px] font-mono">
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
              <span className="text-slate-500 block text-[9px]">Ablation Protocol SHA-256</span>
              <span className="text-slate-300 break-all select-all">
                b3d6945e90c46d76310241a2168c7e9e8e8e506589d17e4cb878d547e47dfe7e
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
              <span className="text-slate-500 block text-[9px]">Champion Forecaster Artifact</span>
              <span className="text-slate-300 break-all select-all">
                c84f67c29e18b14a60032b490f230ec2b71fae8c679a95781d4cb2f57ef518c0
              </span>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition-colors"
          >
            Close Drawer
          </button>
        </div>
      </div>
    </div>
  );
}
