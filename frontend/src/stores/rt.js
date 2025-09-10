// src/stores/rt.js
// Realtime 情報のPiniaストア：1分ごとにA→B→A→B…と交互に叩き、変化時のみ通知ログに積む
//
// state:
//   - lastBySpot: 最新RTDoc（スポット別）
//   - notifyLog: 変更イベントの履歴（トースト等の通知で使用）
//   - timerId: setTimeout のID（nullで停止）
//   - cursor: 現在叩くスポットのインデックス
//   - spotOrder: ポーリング対象の spot_id 配列（ナビ plan の waypoints 由来）
//
// actions:
//   - startPolling(waypoints): 60秒間隔で1スポットずつ順繰りにGET
//   - stopPolling(): ポーリング停止
//   - tick(): 実1回分のフェッチ＆差分判定
//   - reset(): クリア
//
// getters:
//   - getLatest(spotId): そのスポットの最新RTDoc or null
//
// 比較ルール（変更検知）:
//   - w, u, c は常に比較
//   - h は (u > 0) のときだけ比較対象。u=0のときは無視（undefined扱い）

import { defineStore } from 'pinia'
import { fetchSpotRT } from '@/lib/realtime' // @ は src エイリアス想定。未設定なら相対に変更: '../lib/realtime'

const POLL_INTERVAL_MS = 60_000

/**
 * @typedef {Object} RTDoc
 * @property {string} s
 * @property {number} w
 * @property {number} u
 * @property {number=} h
 * @property {number} c
 */

/**
 * @typedef {{ spot_id: string } | string} WaypointRef
 */

export const useRtStore = defineStore('rt', {
  state: () => ({
    /** @type {Record<string, RTDoc>} */
    lastBySpot: {},
    /** @type {Array<{ spot_id: string, prev: RTDoc|null, next: RTDoc, at: number }>} */
    notifyLog: [],
    /** @type {number|null} */
    timerId: null,
    /** @type {number} */
    cursor: 0,
    /** @type {string[]} */
    spotOrder: []
  }),

  getters: {
    /**
     * 最新のRTDocを返す（なければ null）
     * @returns {(spotId: string) => RTDoc | null}
     */
    getLatest: (state) => (spotId) => state.lastBySpot[spotId] ?? null
  },

  actions: {
    /**
     * Waypoints配列から spot_id の順序配列をセット
     * @param {WaypointRef[]} waypoints
     */
    setSpotOrder(waypoints) {
      const order = []
      for (const wp of waypoints ?? []) {
        if (typeof wp === 'string') {
          order.push(wp)
        } else if (wp && typeof wp === 'object' && 'spot_id' in wp && wp.spot_id) {
          order.push(String(wp.spot_id))
        }
      }
      this.spotOrder = order
      // カーソルはリセット（A→B→A→B… を1から）
      this.cursor = 0
    },

    /**
     * ポーリング開始（60秒ごとに1スポットだけ叩く）
     * @param {WaypointRef[]} waypoints
     */
    startPolling(waypoints) {
      this.setSpotOrder(waypoints)
      // 既に動作中なら一旦止める
      this.stopPolling()
      if (this.spotOrder.length === 0) {
        return
      }
      // すぐに1回叩いてからスケジュール
      this._tickAndSchedule()
    },

    /**
     * 停止
     */
    stopPolling() {
      if (this.timerId !== null) {
        clearTimeout(this.timerId)
        this.timerId = null
      }
    },

    /**
     * 内部：tick実行後、次回を予約
     */
    _tickAndSchedule() {
      // 実行
      this.tick().finally(() => {
        // ドリフトを避けるため setTimeout で逐次スケジュール
        this.timerId = setTimeout(() => this._tickAndSchedule(), POLL_INTERVAL_MS)
      })
    },

    /**
     * 1スポット分の取得＆差分判定（A→B→A→B...の1ステップ）
     */
    async tick() {
      if (this.spotOrder.length === 0) return
      // 現在のスポット
      const spotId = this.spotOrder[this.cursor]
      // 次回カーソルを先に進めておく
      this.cursor = (this.cursor + 1) % this.spotOrder.length

      const { status, body } = await fetchSpotRT(spotId)

      if (status === 204 || status === 0) {
        // 204=未到達, 0=失敗 → 何もしない（次周期へ）
        return
      }
      if (status !== 200 || !body) {
        return
      }

      // 差分判定
      const prev = this.lastBySpot[spotId] ?? null
      const next = /** @type {RTDoc} */ (body)
      const changed = !this._isSame(prev, next)

      // 最新値を更新
      this.lastBySpot[spotId] = next

      // 変更があれば通知ログに積む
      if (changed) {
        this.notifyLog.push({
          spot_id: spotId,
          prev,
          next,
          at: Date.now()
        })
      }
    },

    /**
     * 変更検知（w,u,c は常に、h は u>0 のときのみ比較）
     * @param {RTDoc|null} a
     * @param {RTDoc} b
     * @returns {boolean} same?
     */
    _isSame(a, b) {
      if (!a) return false
      if (a.w !== b.w) return false
      if (a.u !== b.u) return false
      if (a.c !== b.c) return false
      // hの扱い：u>0のときだけ比較。u==0なら両方無視（undefined扱い）
      if (b.u > 0) {
        // a側もu>0でなければ差分とみなす
        if (a.u <= 0) return false
        const ah = typeof a.h === 'number' ? a.h : undefined
        const bh = typeof b.h === 'number' ? b.h : undefined
        if (ah !== bh) return false
      }
      return true
    },

    /**
     * 全消去（ナビ終了時など）
     */
    reset() {
      this.stopPolling()
      this.lastBySpot = {}
      this.notifyLog = []
      this.cursor = 0
      this.spotOrder = []
    }
  }
})
