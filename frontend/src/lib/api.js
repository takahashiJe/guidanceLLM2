// src/lib/api.js
const BACK_BASE = '/back';              // Nginxで /back → APIゲートウェイにリバースプロキシ
const API_BASE  = `${BACK_BASE}/api`;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function apiFetch(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  };
  const init = {
    method: 'GET',
    ...opts,
    headers,
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

/** POST /route → 経路計画を同期取得 */
export async function createRoutePlan(options) {
  if (!options) throw new Error('options is required');
  const {
    language,
    origin,
    waypoints,
    return_to_origin = true,
  } = options;
  const payload = {
    language,
    origin,
    waypoints: (waypoints || []).map((w) => ({ spot_id: w.spot_id })),
    return_to_origin,
  };
  const { status, body } = await apiFetch('/route', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (status !== 200) throw new Error(`unexpected status ${status}`);
  return body;
}

/** POST /nav/plan → { task_id } (202) */
export async function startNavigationTask(routePayload) {
  const { status, body } = await apiFetch('/nav/plan', {
    method: 'POST',
    body: JSON.stringify(routePayload),
  });
  if (status !== 202) throw new Error(`unexpected status ${status}`);
  if (!body?.task_id) throw new Error('no task_id');
  return body; // { task_id }
}

/**
 * 互換用: 旧 createPlan は Routing→NAV を一括実行していた。
 * 分離後も呼び出し箇所を壊さないよう、入力内容を見て適切に委譲する。
 */
export async function createPlan(payload) {
  if (!payload) throw new Error('payload is required');

  // 新形式: 既に routing 結果を含む場合はそのまま NAV タスクを開始
  if (payload.route || payload.polyline || payload.segments || payload.legs) {
    const navPayload = {
      buffer: payload.buffer || { car: 300, foot: 10 },
      ...payload,
    };
    return startNavigationTask(navPayload);
  }

  // 旧形式: routing 未実行の場合はここで routing → NAV を直列で呼び出す
  const routeResult = await createRoutePlan(payload);
  const navPayload = {
    language: payload.language,
    buffer: payload.buffer || { car: 300, foot: 10 },
    route: routeResult.feature_collection,
    polyline: routeResult.polyline,
    segments: routeResult.segments,
    legs: routeResult.legs,
    waypoints_info: routeResult.waypoints_info,
  };
  return startNavigationTask(navPayload);
}

/** GET /nav/plan/tasks/:id を 200になるまでポーリングし、PlanResponse を返す */
export async function pollPlan(taskId, onTick) {
  let attempt = 0;
  while (true) {
    const { status, body } = await apiFetch(
      `/nav/plan/tasks/${encodeURIComponent(taskId)}?ts=${Date.now()}`
    );
    if (status === 200) return body;        // 最終レスポンス
    if (status === 202) {                   // 進捗
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

/** GET /nav/plan/tasks/:id → 単発取得（202/200どちらでもボディを返す） */
export async function getPlanResult(taskId) {
  const { body } = await apiFetch(
    `/nav/plan/tasks/${encodeURIComponent(taskId)}?ts=${Date.now()}`
  );
  return body;
}

// --- Realtime (LoRaWAN/MQTT) ---
export async function fetchRealtimeBySpotId(spotId, opts = {}) {
  const headers = {}
  if (opts && Object.prototype.hasOwnProperty.call(opts, 'etag')) {
    headers['If-None-Match'] = String(opts.etag)
  }

  const requestOptions = Object.keys(headers).length ? { headers } : {}

  const { status, body } = await apiFetch(`/rt/spot/${encodeURIComponent(spotId)}`, requestOptions);
  if (status === 204 || status === 304) {
    return { status, body: null }
  }
  return { status, body }
}

// 互換用エイリアス（既存コード対策）
export const fetchPlanResult = pollPlan;
export const fetchPlanTask   = pollPlan;
