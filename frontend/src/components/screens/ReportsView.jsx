import React, { useState } from 'react';
import { 
  FileDown, 
  FileSpreadsheet, 
  FileCode, 
  Bell, 
  CheckCircle2, 
  ShieldCheck, 
  ExternalLink,
  MessageSquare,
  Mail
} from 'lucide-react';
import { getExportCsvUrl, getExportJsonUrl } from '../../api/client';

export default function ReportsView({ analysisId = 'anl_sample_prod_01', tenantId = 'tenant_demo' }) {
  const [emailDigest, setEmailDigest] = useState(true);
  const [slackWebhook, setSlackWebhook] = useState(false);
  const [digestEmail, setDigestEmail] = useState('finops-alerts@organization.com');
  const [slackUrl, setSlackUrl] = useState('https://hooks.slack.com/services/T000/B000/XXXX');
  const [saveBanner, setSaveBanner] = useState(false);

  const csvUrl = getExportCsvUrl(analysisId, tenantId);
  const jsonUrl = getExportJsonUrl(analysisId, tenantId);

  const handleSaveDigest = (e) => {
    e.preventDefault();
    setSaveBanner(true);
    setTimeout(() => setSaveBanner(false), 3000);
  };

  return (
    <div className="py-8 px-4 sm:px-6 max-w-5xl mx-auto space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight">Reports & Digest Notifications</h1>
        <p className="text-xs text-slate-400 mt-0.5">Export verified audit trails and configure proactive incident digests.</p>
      </div>

      {saveBanner && (
        <div className="p-4 rounded-xl bg-teal-950/60 border border-teal-500/30 text-teal-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-teal-400" />
          <span>Digest notification preferences updated successfully.</span>
        </div>
      )}

      {/* Export Options Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* CSV Export */}
        <div className="glass-card p-6 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 mb-4">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <h2 className="text-base font-bold text-white mb-2">Sanitized CSV Incident Report</h2>
            <p className="text-xs text-slate-400 leading-relaxed mb-4">
              Export complete tabular anomaly records formatted for Microsoft Excel and Google Sheets. Protected with automatic CSV formula injection sanitization.
            </p>
            <div className="flex items-center gap-2 text-[11px] text-teal-400 font-mono mb-6">
              <ShieldCheck className="w-4 h-4" />
              <span>DDE Formula Injection Neutralized</span>
            </div>
          </div>
          <a
            href={csvUrl}
            download={`driftsense_anomalies_${analysisId}.csv`}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-xs shadow-md shadow-teal-500/20 transition-all text-center"
          >
            <FileDown className="w-4 h-4" />
            <span>Download Anomalies CSV</span>
          </a>
        </div>

        {/* JSON Audit Export */}
        <div className="glass-card p-6 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4">
              <FileCode className="w-5 h-5" />
            </div>
            <h2 className="text-base font-bold text-white mb-2">Cryptographic JSON Audit Log</h2>
            <p className="text-xs text-slate-400 leading-relaxed mb-4">
              Export full machine-readable JSON telemetry including analysis ID, operational events, raw feature values, and TreeSHAP attribution outputs.
            </p>
            <div className="flex items-center gap-2 text-[11px] text-indigo-400 font-mono mb-6">
              <ShieldCheck className="w-4 h-4" />
              <span>Full Provenance & Hash Trail Included</span>
            </div>
          </div>
          <a
            href={jsonUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs border border-slate-700 transition-all text-center"
          >
            <ExternalLink className="w-4 h-4" />
            <span>Export Raw JSON Audit</span>
          </a>
        </div>
      </div>

      {/* Weekly Digest Preferences Form */}
      <div className="glass-card p-6 rounded-2xl">
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-5 h-5 text-purple-400" />
          <h2 className="text-base font-bold text-white">Automated Digest Notifications</h2>
        </div>
        <p className="text-xs text-slate-400 mb-6">
          Receive scheduled executive summaries of weekly cloud cost movements and newly flagged anomalies.
        </p>

        <form onSubmit={handleSaveDigest} className="space-y-4 text-xs">
          {/* Email Digest */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-white font-medium cursor-pointer">
                <Mail className="w-4 h-4 text-teal-400" />
                <span>Weekly Finance Email Digest</span>
              </label>
              <input
                type="checkbox"
                checked={emailDigest}
                onChange={(e) => setEmailDigest(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-teal-500 focus:ring-teal-500"
              />
            </div>
            {emailDigest && (
              <input
                type="email"
                value={digestEmail}
                onChange={(e) => setDigestEmail(e.target.value)}
                placeholder="finops-alerts@organization.com"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono outline-none focus:border-teal-500"
              />
            )}
          </div>

          {/* Slack Webhook */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-white font-medium cursor-pointer">
                <MessageSquare className="w-4 h-4 text-purple-400" />
                <span>Slack Incident Webhook</span>
              </label>
              <input
                type="checkbox"
                checked={slackWebhook}
                onChange={(e) => setSlackWebhook(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-teal-500 focus:ring-teal-500"
              />
            </div>
            {slackWebhook && (
              <input
                type="text"
                value={slackUrl}
                onChange={(e) => setSlackUrl(e.target.value)}
                placeholder="https://hooks.slack.com/services/..."
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono outline-none focus:border-teal-500"
              />
            )}
          </div>

          <button
            type="submit"
            className="px-6 py-2 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-xs shadow-md shadow-teal-500/20"
          >
            Save Notification Settings
          </button>
        </form>
      </div>
    </div>
  );
}
