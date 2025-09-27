// src/lib/api.js
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

/**
 * 内部ヘルパー: APIを叩き、{ status, body } を返す
 */
async function apiFetch(path, opts = {}) {
  const url = `${API_BASE}${path}`
  const init = {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    ...opts
  }
  console.debug('[api]', init.method, path)

  try {
    const res = await fetch(url, init)
    const txt = await res.text()
    let body
    try {
      body = txt ? JSON.parse(txt) : {}
    } catch {
      body = txt
    }

    console.debug('[api]', init.method, 'status', res.status)
    if (res.status >= 400 && res.status !== 202) {
      const err = new Error(`HTTP ${res.status}`)
      err.status = res.status
      err.body = body
      throw err
    }
    return { status: res.status, body }
  } catch (err) {
    console.error('[api] fetch failed', err)
    // ネットワークエラーなどを吸収
    err.status = err.status || 0
    throw err
  }
}

// --- ★★★ ここからが修正箇所 ★★★ ---

/**
 * 【新規】経路計画APIを呼び出す
 * @param {object} options - ルート作成のオプション
 * @returns {Promise<object>} ルート情報を含むレスポンスボディ
 */
export const createRoutePlan = async (options) => {
  const { language, origin, waypoints, return_to_origin = true } = options
  const payload = {
    language,
    origin,
    waypoints: waypoints.map((w) => ({ spot_id: w.spot_id })),
    return_to_origin
  }
  const { status, body } = await apiFetch('/route', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
  if (status !== 200) throw new Error(`API error: status ${status}`)
  return body
}

/**
 * 【新規】ナビゲーション（ガイダンス生成）タスクを開始する
 * @param {object} routeData - createRoutePlanから返された経路情報オブジェクト全体
 * @returns {Promise<object>} 開始されたタスクの情報 { task_id: string }
 */
export const startNavigationTask = async (routeData) => {
  const { status, body } = await apiFetch('/nav/plan', {
    method: 'POST',
    body: JSON.stringify(routeData)
  })
  if (status !== 202) throw new Error(`unexpected status ${status}`)
  if (!body?.task_id) throw new Error('no task_id')
  return body
}

/**
 * 【新規】タスクの実行結果を取得する
 * この関数はポーリングロジックを持たず、一度だけ結果を取得する
 * @param {string} taskId
 * @returns {Promise<object>} タスクの現在の結果
 */
export const getPlanResult = async (taskId) => {
  const { body } = await apiFetch(`/nav/plan/tasks/${encodeURIComponent(taskId)}?ts=${Date.now()}`)
  return body
}


// --- ★★★ 以下の fetchRealtimeBySpotId はリファクタリングに関係ないため、そのまま維持 ★★★ ---

/**
 * 指定されたスポットのリアルタイム情報を取得する。
 * @param {string} spotId - The ID of the spot.
 * @param {object} opts - Options for the request.
 * @param {string} opts.etag - The ETag for caching.
 * @returns {Promise<{status: number, body: object|null}>}
 */
export async function fetchRealtimeBySpotId(spotId, opts = {}) {
  const { etag } = opts
  const headers = {}
  if (etag) headers['if-none-match'] = etag
  const { status, body } = await apiFetch(`/rt/spot/${encodeURIComponent(spotId)}`, { headers })
  if (status === 304) return { status, body: null }
  if (status === 200) return { status, body }
  return { status, body: null }
}