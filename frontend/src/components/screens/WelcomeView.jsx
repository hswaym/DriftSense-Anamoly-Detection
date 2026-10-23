import React from 'react';
import { 
  CloudLightning, 
  Sparkles, 
  Database, 
  ArrowRight, 
  Layers, 
  CheckCircle2, 
  Lock, 
  TrendingUp, 
  FileCheck 
} from 'lucide-react';

export default function WelcomeView({ onTryDemo, onUploadClick }) {
  return (
    <div className="py-12 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
      {/* Hero Header */}
      <div className="text-center max-w-3xl mx-auto mb-14">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/10 border border-teal-500/20 text-teal-300 text-xs font-semibold mb-6 shadow-sm">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Production FinOps Intelligence v2.0</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white mb-6 leading-tight">
          Cloud cost anomalies detected with <span className="text-brand-gradient">calibrated attribution</span> and zero jargon.
        </h1>
        <p className="text-base sm:text-lg text-slate-300 leading-relaxed font-normal mb-8">
          DriftSense explains why your AWS, Azure, or GCP billing shifted in plain language, decomposes price versus volume drivers, and provides executive briefings your finance leads actually trust.
        </p>

        {/* Call to Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button
            onClick={onTryDemo}
            className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-6 py-3.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-sm shadow-lg shadow-teal-500/25 transition-all transform hover:-translate-y-0.5"
          >
            <Database className="w-4 h-4" />
            <span>Try with Sample Data</span>
          </button>
          <button
            onClick={onUploadClick}
            className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-6 py-3.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 font-semibold text-sm transition-all transform hover:-translate-y-0.5"
          >
            <span>Upload your cloud bill</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Feature Pillar Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
        <div className="glass-card glass-card-hover p-6 rounded-2xl">
          <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400 mb-4">
            <Layers className="w-5 h-5" />
          </div>
          <h2 className="text-lg font-bold text-white mb-2">Multi-Layer Attribution</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Decomposes every incident into rate shifts, volume consumption, and resource mix instead of opaque black-box guesses.
          </p>
        </div>

        <div className="glass-card glass-card-hover p-6 rounded-2xl">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 mb-4">
            <FileCheck className="w-5 h-5" />
          </div>
          <h2 className="text-lg font-bold text-white mb-2">Non-Causal Language Guard</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Synthesizes executive narratives strictly compliant with non-causal copy validation—no hallucinated claims of root cause.
          </p>
        </div>

        <div className="glass-card glass-card-hover p-6 rounded-2xl">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400 mb-4">
            <Lock className="w-5 h-5" />
          </div>
          <h2 className="text-lg font-bold text-white mb-2">100% Tenant Isolation</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Strict isolation boundaries, automated CSV injection formula guards, and memory budgets designed for enterprise security.
          </p>
        </div>
      </div>

      {/* Trust & Provenance Bar */}
      <div className="border border-slate-800/80 rounded-2xl p-6 bg-slate-900/40 backdrop-blur flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-teal-400" />
          <span>Compatible with <strong>FinOps Open Cost & Usage Spec (FOCUS 1.0)</strong>, AWS CUR 2.0, Azure, and GCP</span>
        </div>
        <div className="flex items-center gap-6 text-[11px] font-mono text-slate-500">
          <span>SHA-256 Provenance Frozen</span>
          <span>178 Passing Verification Tests</span>
        </div>
      </div>
    </div>
  );
}
