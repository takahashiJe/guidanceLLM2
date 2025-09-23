// src/lib/spotCodes.js
// POI.json を元に spot_id → 1バイト code (0..255) の対応表を作るユーティリティ。
// - 生成は buildSpotCodeMap() をアプリ起動時に一度だけ呼べばOK。
// - getCode(spotId), getSpotId(code) で双方向取得ができます。

// Vite などのモダン環境では JSON を直接 import できます。
// 例: [{ "spot_id": "spot_001", "name": "..." }, ...]
import POI from '@/assets/POI.json'

/** @type {Record<string, number>} */
let spotCodeMap = Object.create(null)
/** @type {Record<number, string>} */
let codeToSpotMap = Object.create(null)
/** @type {boolean} */
let built = false

/**
 * 生成ポリシー:
 *  - POI.json を spot_id の昇順でソートし、0..N-1 の連番を割り振る
 *  - 256 件を超える場合は 255 以降は割り当てずスキップ（LoRa 1バイト制約）
 *  - 重複 spot_id は無視
 */

/**
 * マップを構築（アプリ起動時に一度呼ぶ）
 * @param {Object} [opts]
 * @param {'by_id'|'by_name'|'file'} [opts.order='by_id'] 割当順序
 * @param {number} [opts.maxCodes=256] 最大コード数（1バイトなら256）
 */
export function buildSpotCodeMap (opts = {}) {
  if (built) return
  const order = opts.order || 'by_id'
  const maxCodes = typeof opts.maxCodes === 'number' ? opts.maxCodes : 256

  /** @type {Array<{spot_id: string, name?: string}>} */
  const list = Array.isArray(POI) ? POI.filter(x => x && x.spot_id) : []

  // 順序決定
  if (order === 'by_name') {
    list.sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
  } else if (order === 'by_id') {
    list.sort((a, b) => String(a.spot_id).localeCompare(String(b.spot_id)))
  } // 'file' のときは元順序のまま

  // 連番割当
  const limit = Math.min(maxCodes, 256)
  let code = 0
  for (const item of list) {
    if (code >= limit) break
    const sid = String(item.spot_id)
    if (spotCodeMap[sid] != null) continue // 重複はスキップ
    spotCodeMap[sid] = code
    codeToSpotMap[code] = sid
    code++
  }

  built = true
}

/**
 * spot_id から 1バイト code を取得
 * @param {string} spotId
 * @returns {number|null}
 */
export function getCode (spotId) {
  if (!built) buildSpotCodeMap()
  const v = spotCodeMap[String(spotId)]
  return (typeof v === 'number') ? v : null
}

/**
 * code (0..255) から spot_id を取得
 * @param {number} code
 * @returns {string|null}
 */
export function getSpotId (code) {
  if (!built) buildSpotCodeMap()
  const v = codeToSpotMap[Number(code)]
  return (typeof v === 'string') ? v : null
}

/**
 * spot_id -> code の生マップを取得（読み取り専用で使ってください）
 * @returns {Record<string, number>}
 */
export function getSpotCodeMap () {
  if (!built) buildSpotCodeMap()
  return spotCodeMap
}

/**
 * code -> spot_id の生マップを取得（読み取り専用で使ってください）
 * @returns {Record<number, string>}
 */
export function getCodeToSpotMap () {
  if (!built) buildSpotCodeMap()
  return codeToSpotMap
}
