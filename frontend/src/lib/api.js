// src/lib/api.js
const BASE = '/back/api';

function log(...args) {
  // 最小限のロガー
  try { console.log('[api]', ...args); } catch (_) {}
}

export async function createPlan(payload) {
  const url = `${BASE}/nav/plan`;
  log('POST', url, payload);
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    body: JSON.stringify(payload),
  });
  log('POST status', res.status);
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`createPlan failed: ${res.status} ${txt}`);
  }
  const json = await res.json();
  log('POST body', json);
  return json;
}

export async function fetchPlanTask(taskId) {
  const url = `${BASE}/nav/plan/tasks/${encodeURIComponent(taskId)}?ts=${Date.now()}`;
  log('GET', url);
  const res = await fetch(url, {
    method: 'GET',
    cache: 'no-store',
    headers: {
      'Cache-Control': 'no-cache, no-store, max-age=0, must-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0',
    },
  });
  log('GET status', res.status);

  if (res.status === 200) {
    try {
      const body = await res.json();
      log('GET body(200)', body);
      return { status: 200, body };
    } catch (e) {
      const txt = await res.text().catch(() => '');
      throw new Error(`fetchPlanTask JSON parse failed: ${e?.message || e}\n${txt}`);
    }
  }

  if (res.status === 500) {
    let body = null;
    try { body = await res.json(); } catch (_) {
      const txt = await res.text().catch(() => '');
      body = { detail: txt || 'server error' };
    }
    log('GET body(500)', body);
    return { status: 500, body };
  }

  // 202/303/その他
  let body = null;
  try { body = await res.json(); } catch (_) {}
  log(`GET body(${res.status})`, body);
  return { status: res.status, body };
}
