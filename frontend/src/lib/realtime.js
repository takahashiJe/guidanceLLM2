// src/lib/realtime.js
// Realtime (LoRa/MQTTブリッジ) API ラッパ（api.js の関数を薄くラップ）
//
// api.js の fetchRealtimeBySpotId() は:
//   - 204 の場合 null を返す
//   - 200 の場合 RTDoc を返す
// ので、ここで {status, body} 形式に正規化して返す。

import { fetchRealtimeBySpotId } from './api' // ← apiFetch ではなく、公開関数を使用
// ★ 追加: LoRa ブリッジ（存在すればオフライン時に利用）
import { isAvailable as loraAvailable, fetchViaLoRa } from './loraBridge'

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
 * - オンライン: HTTP（従来どおり）
 * - オフライン かつ LoRa 利用可: LoRa 経由（downlink省略時は null→204）
 * @param {string} spotId
 * @param {{ etag?: number }=} opts  // 省略可。LoRa利用時のみ有効（変更なしなら downlink省略→null）
 * @returns {Promise<{status:number, body: RTDoc|null, error?:any}>}
 */
export async function fetchSpotRT(spotId, opts = {}) {
  try {
    const online = typeof navigator !== 'undefined' ? !!navigator.onLine : true

    // ★ オフライン時は LoRa に自動フォールバック（利用可能な場合のみ）
    if (!online && loraAvailable && loraAvailable()) {
      const doc = await fetchViaLoRa(spotId, opts.etag)
      if (doc == null) {
        // downlink省略（変更なし） or 取得失敗 → 204 とみなす
        return { status: 204, body: null }
      }
      return { status: 200, body: /** @type {RTDoc} */ (doc) }
    }

    // ★ 従来どおり HTTP を使用（オンライン時 or LoRa未利用時）
    const result = await fetchRealtimeBySpotId(spotId) // 200ならRTDoc、204ならnull
    if (result === null) {
      return { status: 204, body: null }
    }
    return { status: 200, body: /** @type {RTDoc} */ (result) }
  } catch (err) {
    return { status: 0, body: null, error: err }
  }
}
