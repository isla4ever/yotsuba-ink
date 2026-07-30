import type { ProviderProfile, ProviderReadinessReport, ProviderTemplate } from '../contracts';

export type ProviderTestResult = {
  ok: boolean;
  provider_id: string;
  kind: ProviderProfile['kind'];
  model?: string;
  error_code: string;
  message: string;
  response_preview?: string;
};

export type ProviderModelDiscoveryResult = {
  ok: boolean;
  provider_id: string;
  kind: ProviderProfile['kind'];
  models: string[];
  added_models: string[];
  error_code: string;
  message: string;
};

export async function listProviderProfiles(): Promise<ProviderProfile[]> {
  const response = await fetch('/api/providers');
  if (!response.ok) throw await providerApiError(response, '/api/providers');
  return response.json();
}

export async function listProviderTemplates(): Promise<ProviderTemplate[]> {
  const response = await fetch('/api/providers/templates');
  if (!response.ok) throw await providerApiError(response, '/api/providers/templates');
  return response.json();
}

export async function saveProviderProfile(provider: ProviderProfile): Promise<ProviderProfile> {
  const response = await postJson('/api/providers', provider);
  return response.json();
}

export async function deleteProviderProfile(providerId: string): Promise<{ ok: boolean; provider_id: string }> {
  const response = await fetch(`/api/providers/${encodeURIComponent(providerId)}`, { method: 'DELETE' });
  if (!response.ok) throw await providerApiError(response, `/api/providers/${providerId}`);
  return response.json();
}

export async function setDefaultProviderProfile(
  providerId: string,
  kind: ProviderProfile['kind'],
): Promise<ProviderProfile[]> {
  const response = await postJson('/api/providers/default', { provider_id: providerId, kind });
  return response.json();
}

export async function saveProviderSecret(providerId: string, apiKey: string): Promise<{ ok: boolean; has_saved_secret: boolean }> {
  const response = await postJson(`/api/providers/${providerId}/secret`, { api_key: apiKey });
  return response.json();
}

export async function testProviderConnection(provider: ProviderProfile, apiKey = ''): Promise<ProviderTestResult> {
  const response = await postJson('/api/providers/test', {
    provider,
    api_key: apiKey,
    prompt: '你好，请用一句话回复。',
  });
  return response.json();
}

export async function getProviderReadiness(workflowId: string): Promise<ProviderReadinessReport> {
  const response = await postJson('/api/providers/readiness', { workflow_id: workflowId });
  return response.json();
}

export async function discoverProviderModels(
  providerId: string,
  apiKey = '',
): Promise<ProviderModelDiscoveryResult> {
  const response = await postJson(`/api/providers/${encodeURIComponent(providerId)}/models/discover`, {
    api_key: apiKey,
  });
  return response.json();
}

async function postJson(url: string, body: unknown) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await providerApiError(response, url);
  return response;
}

async function providerApiError(response: Response, url: string) {
  let detail = '';
  try {
    const payload = await response.json() as { detail?: unknown };
    detail = typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    // Preserve the endpoint and status when the upstream body is not JSON.
  }
  return new Error(detail || `请求失败：${url} (${response.status})`);
}
