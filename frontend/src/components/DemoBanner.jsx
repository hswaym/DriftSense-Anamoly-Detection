import React from 'react';
import { Database, ArrowRight, X } from 'lucide-react';

export default function DemoBanner({ isDemoMode, setIsDemoMode, onUploadClick }) {
  if (!isDemoMode) return null;

  return (
    <div className="bg-gradient-to-r from-teal-950/80 via-slate-900 to-indigo-950/80 border-b border-teal-500/20 py-2.5 px-4 text-xs font-medium text-slate-300">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-teal-400 animate-pulse" />
          <span className="font-semibold text-teal-300">Sample Data Demo Mode:</span>
          <span>Viewing pre-bundled multi-cloud telemetry ($48,250 spend across EC2, RDS, and S3).</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onUploadClick}
            className="flex items-center gap-1 text-teal-400 hover:text-teal-200 underline font-semibold transition-colors"
          >
            <span>Upload your real cloud bill</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsDemoMode(false)}
            className="text-slate-500 hover:text-slate-300 p-0.5 rounded transition-colors"
            title="Dismiss Demo Banner"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
