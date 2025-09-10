// src/lib/realtime.js
// Realtime (LoRa/MQTTブリッジ) API ラッパ
// - GET /api/rt/spot/:spot_id を叩いて、{ status, body } を返す薄い関数だけ用意
// - 204(No Content)は { status: 204, body: null } を返す
// - 例外は握りつぶして { status: 0, body: null, error } を返す（フロントは無視でOK）

import { apiFetch } from './api' // 既存の共通フェッチ関数を利用（/api ベースは内部で吸収されている想定）

/**
 * @typedef {Object} RTDoc
 * @property {string} s   // spot_id
 * @property {number} w   // now: 0=sun,1=cloud,2=rain
 * @property {number} u   // upcoming: 0=none,1=to_cloud,2=to_rain,3=to_sun
 * @property {number=} h  // hours ahead (only when u>0)
 * @property {number} c   // congestion 0..4
 */

/**
 * 指定スポットのRT情報を取得
 * @param {string} spotId
 * @returns {Promise<{status:number, body: RTDoc|null, error?:any}>}
 */
export async function fetchSpotRT(spotId) {
  const path = `/rt/spot/${encodeURIComponent(spotId)}`
  try {
    const res = await apiFetch(path, { method: 'GET' })
    // 期待：res = { status, body }
    if (!res || typeof res.status !== 'number') {
      return { status: 0, body: null, error: new Error('invalid response') }
    }
    if (res.status === 200) {
      return { status: 200, body: /** @type {RTDoc} */ (res.body) }
    }
    if (res.status === 204) {
      return { status: 204, body: null }
    }
    // それ以外のステータスはエラー扱い
    return { status: res.status, body: null, error: res.body }
  } catch (err) {
    return { status: 0, body: null, error: err }
  }
}
