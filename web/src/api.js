// API client — wired to /api/* (proxied to :7000 in dev; same-origin in prod)

async function request(path, opts = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function fetchIssues({ env, q, include_resolved } = {}) {
  const params = new URLSearchParams();
  if (env) params.set('env', env);
  if (q) params.set('q', q);
  if (include_resolved) params.set('include_resolved', '1');
  return request('/api/issues?' + params.toString());
}

export async function fetchIssue(fp) {
  return request(`/api/issues/${fp}`);
}

export async function fetchOverview({ env } = {}) {
  const params = new URLSearchParams();
  if (env) params.set('env', env);
  return request('/api/overview?' + params.toString());
}

export async function fetchLlm({ env } = {}) {
  const params = new URLSearchParams();
  if (env) params.set('env', env);
  return request('/api/llm?' + params.toString());
}

export async function fetchDeploys({ env } = {}) {
  const params = new URLSearchParams();
  if (env) params.set('env', env);
  return request('/api/deploys?' + params.toString());
}

export async function fetchAlerts({ env } = {}) {
  const params = new URLSearchParams();
  if (env) params.set('env', env);
  return request('/api/alerts?' + params.toString());
}

export async function fetchMeta() {
  return request('/api/meta');
}

export async function resolveIssue(fp) {
  return request(`/api/issues/${fp}/resolve`, { method: 'POST' });
}

export async function reopenIssue(fp) {
  return request(`/api/issues/${fp}/reopen`, { method: 'POST' });
}

export async function createGithubIssue(fp) {
  // The contract returns 400 {"ok": false, "error": "github_not_configured"}
  // when GitHub isn't set up — an expected response the UI turns into a
  // setup hint, not a network failure, so surface the body instead of throwing.
  const res = await fetch(`/api/issues/${fp}/github`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
  });
  if (res.status === 400) return res.json();
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
