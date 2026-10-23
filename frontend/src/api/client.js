/**
 * DriftSense API Client (Phase 12)
 * Connects to FastAPI backend (/uploads, /analyses, /anomalies, /events, /reports).
 * Includes robust fallback demo mode with bundled sample data.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function uploadBillingFile(file, tenantId = 'tenant_demo') {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/uploads`, {
    method: 'POST',
    headers: {
      'X-Tenant-ID': tenantId,
    },
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with HTTP ${res.status}`);
  }

  return res.json();
}

export async function getUploadHealth(uploadId, tenantId = 'tenant_demo') {
  const res = await fetch(`${API_BASE}/uploads/${uploadId}/health`, {
    headers: { 'X-Tenant-ID': tenantId },
  });
  if (!res.ok) throw new Error(`Failed to load health report (${res.status})`);
  return res.json();
}

export async function updateColumnMapping(uploadId, columnMapping, tenantId = 'tenant_demo') {
  const res = await fetch(`${API_BASE}/uploads/${uploadId}/mapping`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
    },
    body: JSON.stringify({ column_mapping: columnMapping }),
  });
  if (!res.ok) throw new Error('Failed to update column mapping');
  return res.json();
}

export async function registerOperationalEvent(eventData, tenantId = 'tenant_demo') {
  const res = await fetch(`${API_BASE}/events`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
    },
    body: JSON.stringify(eventData),
  });
  if (!res.ok) throw new Error('Failed to register event');
  return res.json();
}

export async function startAnalysis(uploadId, minMateriality = 10.0, sensitivity = 'Balanced', tenantId = 'tenant_demo') {
  const res = await fetch(`${API_BASE}/analyses`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
    },
    body: JSON.stringify({
      upload_id: uploadId,
      min_materiality_dollars: minMateriality,
      sensitivity: sensitivity,
    }),
  });
  if (!res.ok) throw new Error('Failed to start analysis');
  return res.json();
}

export async function getAnalysisStatus(analysisId, tenantId = 'tenant_demo') {
  const res = await fetch(`${API_BASE}/analyses/${analysisId}`, {
    headers: { 'X-Tenant-ID': tenantId },
  });
  if (!res.ok) throw new Error('Failed to get analysis status');
  return res.json();
}

export async function getAnalysisOverview(analysisId, tenantId = 'tenant_demo') {
  const res = await fetch(`${API_BASE}/analyses/${analysisId}/overview`, {
    headers: { 'X-Tenant-ID': tenantId },
  });
  if (!res.ok) throw new Error('Failed to get overview');
  return res.json();
}

export async function listAnomalies(analysisId = null, severity = null, service = null, tenantId = 'tenant_demo') {
  const params = new URLSearchParams();
  if (analysisId) params.append('analysis_id', analysisId);
  if (severity) params.append('severity', severity);
  if (service) params.append('service', service);

  const res = await fetch(`${API_BASE}/anomalies?${params.toString()}`, {
    headers: { 'X-Tenant-ID': tenantId },
  });
  if (!res.ok) throw new Error('Failed to list anomalies');
  return res.json();
}

export async function getAnomalyDetail(anomalyId, tenantId = 'tenant_demo') {
  const res = await fetch(`${API_BASE}/anomalies/${anomalyId}`, {
    headers: { 'X-Tenant-ID': tenantId },
  });
  if (!res.ok) throw new Error('Failed to get anomaly detail');
  return res.json();
}

export async function submitAnomalyFeedback(anomalyId, feedback, notes = '', tenantId = 'tenant_demo') {
  const res = await fetch(`${API_BASE}/anomalies/${anomalyId}/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
    },
    body: JSON.stringify({ feedback, notes }),
  });
  if (!res.ok) throw new Error('Failed to submit feedback');
  return res.json();
}

export function getExportCsvUrl(analysisId, tenantId = 'tenant_demo') {
  return `${API_BASE}/reports/${analysisId}.csv`;
}

export function getExportJsonUrl(analysisId, tenantId = 'tenant_demo') {
  return `${API_BASE}/reports/${analysisId}/export.json`;
}
