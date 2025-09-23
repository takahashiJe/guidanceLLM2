// src/lib/api.js
const BACK_BASE = '/back';              // Nginxで /back → APIゲートウェイにリバースプロキシ
const API_BASE  = `${BACK_BASE}/api`;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function apiFetch(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const init = {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  };
  console.debug('[api]', init.method, path);

  const res = await fetch(url, init);
  const txt = await res.text();
  let body;
  try { body = txt ? JSON.parse(txt) : {}; } catch { body = txt; }

  console.debug('[api]', init.method, 'status', res.status);
  if (res.status >= 400 && res.status !== 202) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return { status: res.status, body };
}

/** POST /nav/plan → { task_id } (202) */
export async function createPlan(payload) {
  const { status, body } = await apiFetch('/nav/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (status !== 202) throw new Error(`unexpected status ${status}`);
  if (!body?.task_id) throw new Error('no task_id');
  return body; // { task_id }
}

/** GET /nav/plan/tasks/:id を 200になるまでポーリングし、PlanResponse を返す */
export async function pollPlan(taskId, onTick) {
  let attempt = 0;
  while (true) {
    const { status, body } = await apiFetch(
      `/nav/plan/tasks/${encodeURIComponent(taskId)}?ts=${Date.now()}`
    );

    if (status === 200) return body;       // 最終レスポンス
    if (status === 202) {                  // 進捗
      onTick && onTick({ attempt, state: body?.state, ready: body?.ready === true });
      await sleep(Math.min(1500 + attempt * 200, 3000));
      attempt++;
      continue;
    }
    if (status === 500) {
      const err = new Error('Server error');
      err.body = body;
      throw err;
    }
    const err = new Error(`Unexpected status ${status}`);
    err.body = body;
    throw err;
  }
}

// --- Realtime (LoRaWAN/MQTT) ---
export async function fetchRealtimeBySpotId(spotId) {
  const { status, body } = await apiFetch(`/rt/spot/${encodeURIComponent(spotId)}`);
  if (status === 204) return null;          // 未到達（今は値なし）
  // 期待ペイロード: { s, w(0..2), u(0..3), h?, c(0..4) }
  return body;
}


// 互換用エイリアス（既存コード対策）
export const fetchPlanResult = pollPlan;
export const fetchPlanTask   = pollPlan;
