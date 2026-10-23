import React from 'react';
import { 
  ShieldAlert, 
  LayoutDashboard, 
  Inbox, 
  Compass, 
  FileText, 
  Settings, 
  HelpCircle, 
  Terminal, 
  SlidersHorizontal,
  CloudLightning,
  Sparkles
} from 'lucide-react';

export default function Navbar({ activeScreen, setActiveScreen, isDemoMode, setIsDemoMode, showExpert, setShowExpert }) {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'inbox', label: 'Alerts Inbox', icon: Inbox },
    { id: 'explore', label: 'Explore', icon: Compass },
    { id: 'reports', label: 'Reports', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings },
    { id: 'trust', label: 'Trust & Limitations', icon: HelpCircle },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveScreen('welcome')}>
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-teal-400 flex items-center justify-center shadow-lg shadow-brand-500/20">
              <CloudLightning className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight text-white font-sans">DriftSense</span>
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/30 rounded">v2.0</span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium">FinOps Anomaly Attribution</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeScreen === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveScreen(item.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isActive 
                      ? 'bg-slate-800 text-teal-300 border border-slate-700/60 shadow-sm' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-teal-400' : 'text-slate-400'}`} />
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Right Action Tools */}
          <div className="flex items-center gap-2.5">
            {/* Upload Button */}
            <button
              onClick={() => setActiveScreen('upload')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 shadow-md shadow-teal-500/20 transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Upload Bill</span>
            </button>

            {/* Expert View Toggle */}
            <button
              onClick={() => setShowExpert(!showExpert)}
              title="Toggle Expert Details Drawer (SHAP, Residuals, Hashes)"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                showExpert 
                  ? 'bg-purple-950/40 text-purple-300 border-purple-500/40 shadow-sm shadow-purple-500/10' 
                  : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Expert Mode</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
