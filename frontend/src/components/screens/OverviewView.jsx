import React from 'react';
import { 
  TrendingUp, 
  AlertOctagon, 
  DollarSign, 
  ShieldAlert, 
  ArrowUpRight, 
  CheckCircle2, 
  ArrowRight, 
  Layers,
  Sparkles
} from 'lucide-react';

export default function OverviewView({ analysis, anomalies, onSelectAnomaly, onGoToInbox }) {
  const topAnomaly = anomalies && anomalies.length > 0 ? anomalies[0] : null;

  const totalSpend = analysis?.total_spend || 48250.40;
  const expectedSpend = analysis?.expected_spend || 41800.00;
  const dollarsAtRisk = analysis?.dollars_at_risk || 6450.40;
  const deviationPct = (((totalSpend - expectedSpend) / expectedSpend) * 100).toFixed(1);

  // Group anomalies by severity
  const criticalCount = anomalies?.filter(a => a.severity.toLowerCase() === 'critical').length || 0;
  const highCount = anomalies?.filter(a => a.severity.toLowerCase() === 'high').length || 0;
  const mediumCount = anomalies?.filter(a => a.severity.toLowerCase() === 'medium').length || 0;

  return (
    <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto space-y-8">
      {/* Page Title & Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">FinOps Executive Overview</h1>
          <p className="text-xs text-slate-400 mt-0.5">Continuous telemetry monitoring across all cloud accounts.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-teal-500/10 border border-teal-500/20 text-teal-300 text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-teal-400" />
            Active Monitoring
          </span>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Actual Spend */}
        <div className="glass-card glass-card-hover p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3 text-slate-400">
            <span className="text-xs font-semibold">Actual Spend</span>
            <DollarSign className="w-4 h-4 text-teal-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-white font-mono">
              ${totalSpend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 font-mono">
            vs. ${expectedSpend.toLocaleString(undefined, { minimumFractionDigits: 2 })} forecast
          </p>
        </div>

        {/* Deviation / Shift */}
        <div className="glass-card glass-card-hover p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3 text-slate-400">
            <span className="text-xs font-semibold">Net Cost Shift</span>
            <TrendingUp className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-amber-400 font-mono">
              +{deviationPct}%
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Above baseline expectation
          </p>
        </div>

        {/* Dollars at Risk */}
        <div className="glass-card glass-card-hover p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3 text-slate-400">
            <span className="text-xs font-semibold">Dollars at Risk</span>
            <AlertOctagon className="w-4 h-4 text-red-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-red-400 font-mono">
              ${dollarsAtRisk.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Unexplained or anomalous spend
          </p>
        </div>

        {/* Active Alerts by Severity */}
        <div className="glass-card glass-card-hover p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3 text-slate-400">
            <span className="text-xs font-semibold">Unusual Spend Alerts</span>
            <ShieldAlert className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-white font-mono">
              {anomalies?.length || 0}
            </span>
            <div className="flex items-center gap-1.5 ml-2">
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold badge-critical">{criticalCount} Crit</span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold badge-high">{highCount} High</span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold badge-medium">{mediumCount} Med</span>
            </div>
          </div>
          <p className="text-[11px] text-teal-400 mt-2 cursor-pointer hover:underline" onClick={onGoToInbox}>
            View full alert inbox &rarr;
          </p>
        </div>
      </div>

      {/* Main Attention Card & Service Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Priority Attention Card */}
        <div className="lg:col-span-2 glass-card p-6 rounded-2xl border-l-4 border-l-red-500">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400 animate-ping" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-red-400">What needs attention first</h2>
            </div>
            {topAnomaly && (
              <span className="px-2.5 py-0.5 text-xs font-bold rounded-full badge-critical">
                {topAnomaly.severity}
              </span>
            )}
          </div>

          {topAnomaly ? (
            <div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                <h3 className="text-lg font-extrabold text-white">
                  {topAnomaly.service_name} spend surge: +${topAnomaly.deviation_cost.toLocaleString()} (+{topAnomaly.percentage_deviation.toFixed(0)}%)
                </h3>
                <span className="text-xs font-mono text-slate-400">
                  {new Date(topAnomaly.timestamp).toUTCString().replace(':00 GMT', ' UTC')}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed mb-4">
                Primary contributing factor: <strong>{topAnomaly.top_cause}</strong> with <strong>{topAnomaly.confidence_tier}</strong> confidence. Volume decomposition indicates compute instance count expansion immediately following an autoscaling reconfiguration.
              </p>
              <div className="flex items-center justify-between pt-3 border-t border-slate-800">
                <span className="text-[11px] text-slate-400 font-mono">
                  Anomaly ID: {topAnomaly.anomaly_id}
                </span>
                <button
                  onClick={() => onSelectAnomaly(topAnomaly.anomaly_id)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-xs shadow-md transition-all"
                >
                  <span>Open Full Briefing</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-400 text-xs">
              <CheckCircle2 className="w-8 h-8 text-teal-400 mx-auto mb-2" />
              <span>Zero critical anomalies flagged. All services operating within forecast variance.</span>
            </div>
          )}
        </div>

        {/* Top Moving Services Breakdown */}
        <div className="glass-card p-6 rounded-2xl">
          <h2 className="text-sm font-bold text-white mb-4 flex items-center justify-between">
            <span>Top Moving Cloud Services</span>
            <Layers className="w-4 h-4 text-slate-400" />
          </h2>
          <div className="space-y-4 text-xs font-mono">
            {(analysis?.top_moving_services || [
              { service: 'AmazonEC2', delta: 4700, pct: 23.4 },
              { service: 'AmazonRDS', delta: 1500, pct: 15.2 },
              { service: 'AmazonS3', delta: 250, pct: 3.3 },
            ]).map((s) => {
              const maxDelta = 5000;
              const barWidth = Math.min(100, Math.max(5, (s.delta / maxDelta) * 100));
              return (
                <div key={s.service} className="space-y-1">
                  <div className="flex justify-between text-slate-300">
                    <span className="font-sans font-semibold text-white">{s.service}</span>
                    <span className="text-teal-400">+${s.delta.toLocaleString()} (+{s.pct}%)</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-teal-500 to-teal-400"
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
