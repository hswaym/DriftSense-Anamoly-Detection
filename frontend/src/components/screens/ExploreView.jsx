import React, { useState } from 'react';
import { Compass, Filter, Layers, DollarSign, PieChart, BarChart2 } from 'lucide-react';

export default function ExploreView({ analysis }) {
  const [selectedDimension, setSelectedDimension] = useState('ServiceName');

  const dimensionData = {
    ServiceName: [
      { name: 'AmazonEC2', spend: 24800.00, pct: 51.4, color: 'from-teal-500 to-teal-400' },
      { name: 'AmazonRDS', spend: 11400.00, pct: 23.6, color: 'from-indigo-500 to-indigo-400' },
      { name: 'AmazonS3', spend: 7850.40, pct: 16.3, color: 'from-amber-500 to-amber-400' },
      { name: 'GoogleCloudStorage', spend: 4200.00, pct: 8.7, color: 'from-purple-500 to-purple-400' },
    ],
    RegionName: [
      { name: 'us-east-1 (N. Virginia)', spend: 31200.00, pct: 64.7, color: 'from-teal-500 to-teal-400' },
      { name: 'us-west-2 (Oregon)', spend: 11800.00, pct: 24.5, color: 'from-indigo-500 to-indigo-400' },
      { name: 'eu-central-1 (Frankfurt)', spend: 5250.40, pct: 10.8, color: 'from-amber-500 to-amber-400' },
    ],
    ChargeCategory: [
      { name: 'Usage (On-Demand & Compute)', spend: 38400.00, pct: 79.6, color: 'from-teal-500 to-teal-400' },
      { name: 'Storage & Provisioned IOPS', spend: 8100.40, pct: 16.8, color: 'from-indigo-500 to-indigo-400' },
      { name: 'Data Transfer & Egress', spend: 1750.00, pct: 3.6, color: 'from-amber-500 to-amber-400' },
    ]
  };

  const currentItems = dimensionData[selectedDimension] || dimensionData.ServiceName;

  return (
    <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">Cost Explorer & Drilldown</h1>
          <p className="text-xs text-slate-400 mt-0.5">Slice and dice multi-cloud telemetry across FOCUS 1.0 canonical dimensions.</p>
        </div>

        {/* Dimension Select */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-900 border border-slate-800 rounded-xl text-xs">
          {['ServiceName', 'RegionName', 'ChargeCategory'].map((dim) => (
            <button
              key={dim}
              onClick={() => setSelectedDimension(dim)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                selectedDimension === dim
                  ? 'bg-teal-500 text-slate-950 font-bold shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {dim === 'ServiceName' ? 'Services' : dim === 'RegionName' ? 'Regions' : 'Charge Categories'}
            </button>
          ))}
        </div>
      </div>

      {/* Breakdown Cards & Horizontal Bars */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-card p-6 rounded-2xl">
          <h2 className="text-sm font-bold text-white mb-4 flex items-center justify-between">
            <span>Spend Share by {selectedDimension}</span>
            <BarChart2 className="w-4 h-4 text-slate-400" />
          </h2>

          <div className="space-y-5">
            {currentItems.map((item) => (
              <div key={item.name} className="space-y-1.5 font-mono">
                <div className="flex justify-between text-xs">
                  <span className="font-sans font-semibold text-slate-200">{item.name}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-white font-bold">${item.spend.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    <span className="text-slate-400 w-12 text-right">({item.pct}%)</span>
                  </div>
                </div>
                <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full bg-gradient-to-r ${item.color} transition-all duration-500`}
                    style={{ width: `${item.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Dimension Details Summary */}
        <div className="glass-card p-6 rounded-2xl flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-bold text-white mb-3">Dimension Intelligence</h2>
            <p className="text-xs text-slate-300 leading-relaxed mb-4">
              FOCUS 1.0 normalization unifies divergent multi-cloud meters (such as AWS BoxUsage vs. Azure VM compute) into canonical grains.
            </p>
            <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2 text-xs font-mono">
              <div className="flex justify-between">
                <span className="text-slate-400">Total Analyzed</span>
                <span className="text-white font-bold">${analysis?.total_spend?.toLocaleString() || '48,250.40'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Top Dimension Entity</span>
                <span className="text-teal-400 font-bold">{currentItems[0].name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Dominance Share</span>
                <span className="text-amber-400 font-bold">{currentItems[0].pct}%</span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-400">
            Click on any item in Alerts Inbox to view instance TreeSHAP attribution.
          </div>
        </div>
      </div>
    </div>
  );
}
