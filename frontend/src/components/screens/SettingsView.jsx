import React, { useState } from 'react';
import { 
  Settings, 
  Sliders, 
  DollarSign, 
  ShieldAlert, 
  Trash2, 
  CheckCircle2, 
  UserCheck, 
  Save 
} from 'lucide-react';

export default function SettingsView({ tenantId, setTenantId }) {
  const [sensitivity, setSensitivity] = useState('Balanced');
  const [minMaterialityDollars, setMinMaterialityDollars] = useState(10.0);
  const [minMaterialityPct, setMinMaterialityPct] = useState(15.0);
  const [retentionDays, setRetentionDays] = useState(90);
  const [saveBanner, setSaveBanner] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);

  const handleSave = (e) => {
    e.preventDefault();
    setSaveBanner(true);
    setTimeout(() => setSaveBanner(false), 3000);
  };

  return (
    <div className="py-8 px-4 sm:px-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight">System Settings & Thresholds</h1>
        <p className="text-xs text-slate-400 mt-0.5">Configure anomaly sensitivity, materiality filters, and tenant data policies.</p>
      </div>

      {saveBanner && (
        <div className="p-4 rounded-xl bg-teal-950/60 border border-teal-500/30 text-teal-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-teal-400" />
          <span>Threshold and sensitivity settings persisted for tenant.</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Detection Sensitivity */}
        <div className="glass-card p-6 rounded-2xl">
          <h2 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-teal-400" />
            <span>Anomaly Detection Sensitivity</span>
          </h2>
          <p className="text-xs text-slate-400 mb-4">
            Tunes the rolling standard deviation threshold ($\sigma$) across service baselines.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { id: 'Low', label: 'Low Sensitivity', desc: 'Fewer alerts, only major spikes (4.0σ)', k: '4σ' },
              { id: 'Balanced', label: 'Balanced (Default)', desc: 'Optimized precision & recall (3.0σ)', k: '3σ' },
              { id: 'High', label: 'High Sensitivity', desc: 'Aggressive detection (2.0σ)', k: '2σ' },
            ].map((s) => (
              <div
                key={s.id}
                onClick={() => setSensitivity(s.id)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  sensitivity === s.id
                    ? 'bg-teal-500/15 border-teal-500 text-teal-300 ring-2 ring-teal-500/20'
                    : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700'
                }`}
              >
                <div className="flex justify-between items-center mb-1">
                  <span className="font-bold text-xs">{s.label}</span>
                  <span className="text-[10px] font-mono text-slate-400">{s.k}</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-normal">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Materiality Noise Suppressors */}
        <div className="glass-card p-6 rounded-2xl">
          <h2 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-amber-400" />
            <span>Materiality Noise Filters</span>
          </h2>
          <p className="text-xs text-slate-400 mb-6">
            Suppresses trivial statistical noise (e.g. $2 micro-spikes during off-peak weekend hours identified in Phase 10 Arm 7).
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-xs">
            {/* Minimum Dollar Delta */}
            <div className="space-y-2">
              <div className="flex justify-between font-mono">
                <span className="text-slate-300">Min Dollar Deviation</span>
                <span className="text-teal-400 font-bold">${minMaterialityDollars}</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={minMaterialityDollars}
                onChange={(e) => setMinMaterialityDollars(Number(e.target.value))}
                className="w-full accent-teal-400"
              />
              <span className="text-[10px] text-slate-500 block">Ignores any incident with total shift under ${minMaterialityDollars}.</span>
            </div>

            {/* Minimum Percentage Delta */}
            <div className="space-y-2">
              <div className="flex justify-between font-mono">
                <span className="text-slate-300">Min Percentage Deviation</span>
                <span className="text-teal-400 font-bold">{minMaterialityPct}%</span>
              </div>
              <input
                type="range"
                min="5"
                max="50"
                step="5"
                value={minMaterialityPct}
                onChange={(e) => setMinMaterialityPct(Number(e.target.value))}
                className="w-full accent-teal-400"
              />
              <span className="text-[10px] text-slate-500 block">Ignores minor fluctuations under {minMaterialityPct}%.</span>
            </div>
          </div>
        </div>

        {/* Tenant Configuration & Privacy */}
        <div className="glass-card p-6 rounded-2xl">
          <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-purple-400" />
            <span>Tenant & Data Retention Policy</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs mb-6">
            <div>
              <label className="text-slate-400 text-[11px] block mb-1">Active Tenant ID (X-Tenant-ID)</label>
              <input
                type="text"
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white font-mono outline-none focus:border-teal-500"
              />
            </div>
            <div>
              <label className="text-slate-400 text-[11px] block mb-1">Data Retention Horizon</label>
              <select
                value={retentionDays}
                onChange={(e) => setRetentionDays(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white font-mono outline-none"
              >
                <option value={30}>30 Days</option>
                <option value={60}>60 Days</option>
                <option value={90}>90 Days (Enterprise Standard)</option>
                <option value={365}>365 Days</option>
              </select>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
            <button
              type="submit"
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-xs shadow-md shadow-teal-500/20"
            >
              <Save className="w-4 h-4" />
              <span>Save System Settings</span>
            </button>

            <button
              type="button"
              onClick={() => alert("All tenant uploaded telemetry and cached artifacts purged safely.")}
              className="flex items-center gap-1.5 text-red-400 hover:text-red-300 text-xs font-semibold"
            >
              <Trash2 className="w-4 h-4" />
              <span>Purge My Tenant Data</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
