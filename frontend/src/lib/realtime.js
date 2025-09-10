// src/lib/realtime.js
// Realtime (LoRa/MQTTブリッジ) API ラッパ（api.js の関数を薄くラップ）
//
// api.js の fetchRealtimeBySpotId() は:
//   - 204 の場合 null を返す
//   - 200 の場合 RTDoc を返す
// ので、ここで {status, body} 形式に正規化して返す。

import { fetchRealtimeBySpotId } from './api' // ← apiFetch ではなく、公開関数を使用

/**
 * @typedef {Object} RTDoc
 * @property {string} s   // spot_id
 * @property {number} w   // now: 0=sun,1=cloud,2=rain
 * @property {number} u   // upcoming: 0=none,1=to_cloud,2=to_rain,3=to_sun
 * @property {number=} h  // hours ahead (only when u>0)
 * @property {number} c   // congestion 0..4
 */

/**
 * 指定スポットのRT情報を取得（{status, body} 形式で返却）
 * @param {string} spotId
 * @returns {Promise<{status:number, body: RTDoc|null, error?:any}>}
 */
export async function fetchSpotRT(spotId) {
  try {
    const result = await fetchRealtimeBySpotId(spotId) // 200ならRTDoc、204ならnull
    if (result === null) {
      return { status: 204, body: null }
    }
    return { status: 200, body: /** @type {RTDoc} */ (result) }
  } catch (err) {
    return { status: 0, body: null, error: err }
  }
}
