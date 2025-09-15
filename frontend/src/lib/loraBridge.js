// src/lib/loraBridge.js
// Capacitor Plugin（window.LoRaRT）を安全にラップして、LoRa 経由で RT データを取得する薄い層。
// - ネイティブ側で `window.LoRaRT` を提供（join(), fetch(code, etag), available）する前提。
// - ここでは spot_id から code を引いて fetch し、HTTP と同じ RTDoc 形 {s,w,u,c,h?} に整形して返す。

import { getCode } from './spotCodes'
import { LoRaRT } from '@guidance/lorart'
if (typeof window !== 'undefined' && LoRaRT && !window.LoRaRT) {
  window.LoRaRT = LoRaRT
}


let _joined = false

/**
 * LoRaRT が利用可能かどうか（ネイティブ実装の有無＋join 済みか）を返す
 * @returns {boolean}
 */
export function isAvailable () {
  const has = typeof window !== 'undefined' && window.LoRaRT && typeof window.LoRaRT === 'object'
  const nativeFlag = has && !!window.LoRaRT.available
  return !!(has && (nativeFlag || _joined))
}

/**
 * JOIN（起動時に1度だけ呼べばOK。複数回呼んでも安全に true を返す）
 * @returns {Promise<boolean>}
 */
export async function join () {
  if (isAvailable() && _joined) return true
  try {
    if (!window.LoRaRT || typeof window.LoRaRT.join !== 'function') {
      // ネイティブ層が未ロード／未実装
      return false
    }
    const ok = await window.LoRaRT.join()
    _joined = !!ok
    return _joined
  } catch {
    return false
  }
}

/**
 * LoRa 経由でスポットの RT 情報を取得（HTTP と同じ RTDoc 形に整形）
 * - 成功: { s, w, u, c, h? }
 * - downlink 省略（etag 一致 等）: null
 * - 失敗: null
 * @param {string} spotId
 * @param {number} [etag] 0..255 などの軽ハッシュ（省略可）
 * @returns {Promise<{s:string, w:number, u:number, c:number, h?:number} | null>}
 */
export async function fetchViaLoRa (spotId, etag) {
  try {
    if (!isAvailable()) return null
    if (!window.LoRaRT || typeof window.LoRaRT.fetch !== 'function') return null

    const code = getCode(spotId)
    if (code == null) return null

    // ネイティブの返却想定：null | { w:number, u:number, c:number, h?:number }
    const res = await window.LoRaRT.fetch(code, etag)
    if (!res) return null

    // 基本的なバリデーション
    const w = toInt(res.w)
    const u = toInt(res.u)
    const c = clampInt(res.c, 0, 4)
    const out = { s: String(spotId), w, u, c }
    if (u > 0 && typeof res.h === 'number') {
      out.h = toInt(res.h)
    }
    return out
  } catch {
    return null
  }
}

/* ----------------- 内部ユーティリティ ----------------- */
function toInt (v) {
  const n = Number(v)
  return Number.isFinite(n) ? (n | 0) : 0
}
function clampInt (v, min, max) {
  const n = toInt(v)
  return Math.max(min, Math.min(max, n))
}
