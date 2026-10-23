import React, { useState } from 'react';
import { 
  Search, 
  Filter, 
  ArrowUpDown, 
  AlertCircle, 
  Clock, 
  CheckCircle2, 
  ArrowRight, 
  Layers,
  Sparkles,
  CheckSquare,
  Square
} from 'lucide-react';

export default function AlertsInboxView({ anomalies, onSelectAnomaly }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [serviceFilter, setServiceFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedIds, setSelectedIds] = useState(new Set());

  // Filter list
  const filtered = (anomalies || []).filter((a) => {
    if (severityFilter !== 'ALL' && a.severity.toLowerCase() !== severityFilter.toLowerCase()) return false;
    if (serviceFilter !== 'ALL' && a.service_name.toLowerCase() !== serviceFilter.toLowerCase()) return false;
    if (statusFilter !== 'ALL' && (a.status || 'New').toLowerCase() !== statusFilter.toLowerCase()) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const matchSvc = a.service_name.toLowerCase().includes(q);
      const matchCause = (a.top_cause || '').toLowerCase().includes(q);
      const matchId = (a.anomaly_id || '').toLowerCase().includes(q);
      if (!matchSvc && !matchCause && !matchId) return false;
    }
    return true;
  });

  // Services available for filter dropdown
  const uniqueServices = Array.from(new Set((anomalies || []).map((a) => a.service_name)));

  // Bulk selection toggles
  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((a) => a.anomaly_id)));
    }
  };

  const toggleSelect = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  return (
    <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">Alerts Inbox</h1>
          <p className="text-xs text-slate-400 mt-0.5">Ranked by dollar impact with multi-layer attribution diagnostics.</p>
        </div>
        <span className="text-xs font-mono text-slate-400">
          Showing {filtered.length} of {anomalies?.length || 0} incidents
        </span>
      </div>

      {/* Filter and Search Toolbar */}
      <div className="glass-card p-4 rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search by service, cause, or alert ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-teal-500 outline-none font-mono"
          />
        </div>

        {/* Severity Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400 text-[11px] font-semibold">Severity:</span>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono outline-none"
          >
            <option value="ALL">All Severities</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>

        {/* Service Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400 text-[11px] font-semibold">Service:</span>
          <select
            value={serviceFilter}
            onChange={(e) => setServiceFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono outline-none"
          >
            <option value="ALL">All Services</option>
            {uniqueServices.map((svc) => (
              <option key={svc} value={svc}>{svc}</option>
            ))}
          </select>
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400 text-[11px] font-semibold">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono outline-none"
          >
            <option value="ALL">All Statuses</option>
            <option value="New">New</option>
            <option value="Investigating">Investigating</option>
            <option value="Resolved">Resolved</option>
          </select>
        </div>
      </div>

      {/* Bulk Action Strip if items selected */}
      {selectedIds.size > 0 && (
        <div className="bg-teal-950/60 border border-teal-500/30 p-3 rounded-xl flex items-center justify-between text-xs text-teal-300">
          <span>{selectedIds.size} incident(s) selected</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => alert(`Acknowledged ${selectedIds.size} incidents as Planned.`)}
              className="px-3 py-1 bg-teal-500 text-slate-950 font-bold rounded-lg hover:bg-teal-400 transition-colors"
            >
              Mark Planned
            </button>
            <button
              onClick={() => setSelectedIds(new Set())}
              className="text-slate-400 hover:text-white px-2 py-1"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Alerts Table */}
      <div className="glass-card rounded-2xl overflow-hidden border border-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4 w-10">
                  <button onClick={toggleSelectAll} className="text-slate-400 hover:text-white">
                    {selectedIds.size > 0 && selectedIds.size === filtered.length ? (
                      <CheckSquare className="w-4 h-4 text-teal-400" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>
                </th>
                <th className="py-3 px-4">Cloud Service</th>
                <th className="py-3 px-4">Timestamp (UTC)</th>
                <th className="py-3 px-4 text-right">Actual Cost</th>
                <th className="py-3 px-4 text-right">Deviation ($)</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Top Contributor</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filtered.map((a) => {
                const isSelected = selectedIds.has(a.anomaly_id);
                return (
                  <tr 
                    key={a.anomaly_id} 
                    className={`hover:bg-slate-900/60 transition-colors cursor-pointer ${
                      isSelected ? 'bg-slate-900/40' : ''
                    }`}
                    onClick={() => onSelectAnomaly(a.anomaly_id)}
                  >
                    <td className="py-3.5 px-4" onClick={(e) => { e.stopPropagation(); toggleSelect(a.anomaly_id); }}>
                      <button className="text-slate-400 hover:text-white">
                        {isSelected ? <CheckSquare className="w-4 h-4 text-teal-400" /> : <Square className="w-4 h-4" />}
                      </button>
                    </td>
                    <td className="py-3.5 px-4 font-sans font-bold text-white">
                      {a.service_name}
                    </td>
                    <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                      {new Date(a.timestamp).toISOString().replace('.000Z', 'Z')}
                    </td>
                    <td className="py-3.5 px-4 text-right text-slate-200">
                      ${a.actual_cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3.5 px-4 text-right font-bold text-amber-400">
                      +${a.deviation_cost.toLocaleString(undefined, { minimumFractionDigits: 2 })} (+{a.percentage_deviation.toFixed(0)}%)
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        a.severity.toLowerCase() === 'critical' ? 'badge-critical' :
                        a.severity.toLowerCase() === 'high' ? 'badge-high' :
                        a.severity.toLowerCase() === 'medium' ? 'badge-medium' : 'badge-low'
                      }`}>
                        {a.severity}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-300 font-sans text-xs">
                      {a.top_cause}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        a.status === 'Resolved' ? 'badge-resolved' : 'bg-slate-800 text-slate-300'
                      }`}>
                        {a.status || 'New'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="inline-flex items-center gap-1 text-teal-400 hover:text-teal-200 font-sans font-semibold">
                        Briefing <ArrowRight className="w-3.5 h-3.5" />
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
