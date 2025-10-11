
// src/lib/api.js
import { useNavStore } from '@/stores/nav';

const BACK_BASE = '/back';              // Nginxで /back → APIゲートウェイにリバースプロキシ
const API_BASE  = `${BACK_BASE}/api`;

async function apiFetch(path, opts = {}) {
  const navStore = useNavStore();
  let url = `${API_BASE}${path}`;

  // Inject deviceId as a query parameter for all requests
  if (navStore.deviceId) {
    const separator = url.includes('?') ? '&' : '?';
    url += `${separator}uuid=${navStore.deviceId}`;
  }

  const headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  };

  const init = {
    method: 'GET',
    ...opts,
    headers,
  };

  // For non-GET requests, also inject deviceId into the body if it exists
  if (init.method.toUpperCase() !== 'GET' && init.body) {
    try {
      const payload = JSON.parse(init.body);
      if (navStore.deviceId) {
        payload.uuid = navStore.deviceId;
      }
      init.body = JSON.stringify(payload);
    } catch (e) {
      console.error('Failed to inject deviceId into request body', e);
    }
  }

  console.debug('[api]', init.method, path);
  const res = await fetch(url, init);
  const txt = await res.text();
  let body;
  try { body = txt ? JSON.parse(txt) : {}; } catch { body = txt; }
  console.debug('[api]', init.method, 'status', res.status);
  if (res.status >= 400) { // Removed status 202 from special cases
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

/** POST /nav/plan → PlanResponse (200) */
async function createNavigationPlan(routePayload) {
  const { status, body } = await apiFetch('/nav/plan', {
    method: 'POST',
    body: JSON.stringify(routePayload),
  });
  if (status !== 200) throw new Error(`unexpected status ${status}`);
  return body; // Returns the full plan
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
    // Directly call the new synchronous function
    return createNavigationPlan(navPayload);
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
  // Directly call the new synchronous function
  return createNavigationPlan(navPayload);
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

// Obsolete polling functions and aliases are removed.

// --- User Authentication ---

/** POST /v1/users -> ユーザー新規作成 */
export async function createUser(userName, language = 'ja') {
  const { status, body } = await apiFetch('/v1/users', {
    method: 'POST',
    body: JSON.stringify({ user_name: userName, language }),
  });
  if (status !== 201) throw new Error(`unexpected status ${status}`);
  return body;
}

/** POST /v1/login -> ログイン */
export async function loginUser(userName) {
  const { status, body } = await apiFetch('/v1/login', {
    method: 'POST',
    body: JSON.stringify({ user_name: userName }),
  });
  if (status !== 200) throw new Error(`unexpected status ${status}`);
  return body;
}

/** POST /v1/chat -> AIエージェントとの会話 */
export async function sendChatMessage(userName, userInput, threadId) {
  const payload = {
    user_name: userName,
    user_input: userInput,
    thread_id: threadId,
  };
  const { status, body } = await apiFetch('/v1/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (status !== 200) throw new Error(`unexpected status ${status}`);
  return body;
}
