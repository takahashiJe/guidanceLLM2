<template>
  <div class="nav-view">
    <!-- ローディング -->
    <div v-if="navStore.isLoading" class="loading-overlay">
      <p>案内プランを生成中です...</p>
    </div>

    <!-- プラン本体 -->
    <div v-else-if="plan && plan.waypoints_info" class="nav-container">
      <div class="map-wrapper">
        <!-- 既存の地図コンポーネント -->
        <NavMap ref="navMap" :plan="plan" />
      </div>

      <!-- 右パネル：操作・一覧・RT最新情報 -->
      <div class="side-panel">
        <div class="controls">
          <button @click="toggleSpotList" class="spot-list-toggle">
            {{ isSpotListVisible ? 'リストを隠す' : 'スポット一覧' }}
          </button>
        </div>

        <!-- スポット一覧（周遊スポット） -->
        <section v-if="isSpotListVisible" class="spot-list">
          <h3>周遊スポット</h3>
          <ol class="spot-ol">
            <li v-for="(wp, idx) in sortedWaypoints" :key="wp.spot_id" class="spot-li">
              <div class="spot-row">
                <span class="order-index">{{ idx + 1 }}</span>
                <span class="spot-name">{{ wp.name || wp.spot_id }}</span>
              </div>

              <!-- RT最新情報（常時参照可能） -->
              <div class="rt-latest" v-if="latestById[wp.spot_id]">
                <span class="rt-badge">{{ formatWeather(latestById[wp.spot_id]) }}</span>
                <span class="rt-badge rt-upcoming" v-if="latestById[wp.spot_id].u > 0">
                  {{ formatUpcoming(latestById[wp.spot_id]) }}
                </span>
                <span class="rt-badge rt-cong">
                  混雑: {{ latestById[wp.spot_id].c }}
                </span>
              </div>

              <div class="rt-latest rt-empty" v-else>
                <span class="rt-muted">リアルタイム情報を待機中…</span>
              </div>
            </li>
          </ol>
        </section>

        <!-- （任意）沿道スポット -->
        <section v-if="isSpotListVisible && sortedAlongPois.length" class="poi-list">
          <h3>沿道スポット</h3>
          <ul>
            <li v-for="poi in sortedAlongPois" :key="poi.spot_id">
              {{ poi.name || poi.spot_id }}
            </li>
          </ul>
        </section>
      </div>

      <!-- 画面右上：変更があった時だけ通知（トースト） -->
      <div class="toast-stack">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast"
          role="status"
          @click="dismissToast(t.id)"
        >
          <div class="toast-title">
            {{ t.title }}
          </div>
          <div class="toast-body">
            <div>{{ t.message }}</div>
            <div v-if="t.diff" class="toast-diff">
              <span v-if="t.diff.w">天気: {{ t.diff.w }}</span>
              <span v-if="t.diff.u">／変化: {{ t.diff.u }}</span>
              <span v-if="typeof t.diff.h === 'number'">／{{ t.diff.h }}時間後</span>
              <span v-if="typeof t.diff.c === 'number'">／混雑: {{ t.diff.c }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- プランなし（リダイレクト保険） -->
    <div v-else class="error-view">
      <p>プランが見つかりませんでした。プラン作成に戻ります。</p>
    </div>
  </div>
</template>

<script setup>
/**
 * 既存の NavView の構造を踏襲しつつ、RT(LoRa/MQTT) 連携を最小追加。
 * - navStore.plan から waypoints を取得
 * - 1分ごとに A→B→A→B… の順で /api/rt/spot/:id を叩く（rtストアに実装済み）
 * - 変更があった時のみ通知（toasts）
 * - 各スポットの最新情報（常時参照可能）を一覧に表示
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import NavMap from '@/components/NavMap.vue'

import { useNavStore } from '@/stores/nav'
import { useRtStore } from '@/stores/rt'

// 既存と同名の参照・計算値を維持
const navStore = useNavStore()
const router = useRouter()
const plan = computed(() => navStore.plan)
const navMap = ref(null)
const isSpotListVisible = ref(true)

// 周遊スポット：order_index -> nearest_idx -> そのまま
const sortedWaypoints = computed(() => {
  const w = plan.value?.waypoints_info ?? []
  return [...w].sort((a, b) => {
    const ao = (a.order_index ?? Number.MAX_SAFE_INTEGER)
    const bo = (b.order_index ?? Number.MAX_SAFE_INTEGER)
    if (ao !== bo) return ao - bo
    const an = (a.nearest_idx ?? Number.MAX_SAFE_INTEGER)
    const bn = (b.nearest_idx ?? Number.MAX_SAFE_INTEGER)
    if (an !== bn) return an - bn
    // 最後に spot_id で安定ソート
    return String(a.spot_id).localeCompare(String(b.spot_id))
  })
})

// 沿道POI：order_index -> nearest_idx
const sortedAlongPois = computed(() => {
  const p = plan.value?.along_pois ?? []
  return [...p].sort((a, b) => {
    const ao = (a.order_index ?? Number.MAX_SAFE_INTEGER)
    const bo = (b.order_index ?? Number.MAX_SAFE_INTEGER)
    if (ao !== bo) return ao - bo
    const an = (a.nearest_idx ?? Number.MAX_SAFE_INTEGER)
    const bn = (b.nearest_idx ?? Number.MAX_SAFE_INTEGER)
    return an - bn
  })
})

// === Realtime Store 連携 ===
const rt = useRtStore()

// 最新値を spot_id -> RTDoc の形で使いやすく
const latestById = computed(() => {
  const map = {}
  for (const wp of plan.value?.waypoints_info ?? []) {
    const sid = wp.spot_id
    const doc = rt.getLatest(sid)
    if (doc) map[sid] = doc
  }
  return map
})

// 変更通知（トースト）キュー（シンプル版）
const toasts = ref([])
/** @param {string} id */
const dismissToast = (id) => {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

// 通知を生成（diff を人間可読に変換）
const spotNameById = computed(() => {
  const m = {}
  for (const wp of plan.value?.waypoints_info ?? []) {
    m[wp.spot_id] = wp.name || wp.spot_id
  }
  return m
})

watch(() => rt.notifyLog.length, (len, prev) => {
  if (len <= prev) return
  const ev = rt.notifyLog[len - 1]
  const name = spotNameById.value[ev.spot_id] || ev.spot_id
  const prevMsg = ev.prev ? makeSummary(ev.prev) : '（初回取得）'
  const nextMsg = makeSummary(ev.next)
  const diff = makeDiff(ev.prev, ev.next)

  const id = `${ev.spot_id}-${ev.at}`
  toasts.value.push({
    id,
    title: `更新: ${name}`,
    message: `${prevMsg} → ${nextMsg}`,
    diff
  })
  // 自動で数秒後に消す
  setTimeout(() => dismissToast(id), 5000)
})

// === 表示用の整形 ===
/** @param {import('@/stores/rt').RTDoc} doc */
function formatWeather(doc) {
  // w: 0=sun,1=cloud,2=rain
  return doc.w === 0 ? '☀ 晴れ' : doc.w === 1 ? '☁ 曇り' : '☔ 雨'
}
/** @param {import('@/stores/rt').RTDoc} doc */
function formatUpcoming(doc) {
  // u: 1=to_cloud,2=to_rain,3=to_sun
  if (doc.u === 1) return `${doc.h ?? '?'}時間後に曇り`
  if (doc.u === 2) return `${doc.h ?? '?'}時間後に雨`
  if (doc.u === 3) return `${doc.h ?? '?'}時間後に晴れ`
  return ''
}
/** @param {import('@/stores/rt').RTDoc} doc */
function makeSummary(doc) {
  const now = doc.w === 0 ? '晴れ' : doc.w === 1 ? '曇り' : '雨'
  const up =
    doc.u === 1 ? `${doc.h ?? '?'}時間後に曇り` :
    doc.u === 2 ? `${doc.h ?? '?'}時間後に雨` :
    doc.u === 3 ? `${doc.h ?? '?'}時間後に晴れ` : ''
  const cong = `混雑:${doc.c}`
  return up ? `${now}（${up}）／${cong}` : `${now}／${cong}`
}
/** @param {import('@/stores/rt').RTDoc|null} prev @param {import('@/stores/rt').RTDoc} next */
function makeDiff(prev, next) {
  if (!prev) return { w: next.w, u: next.u, h: next.u > 0 ? next.h : undefined, c: next.c }
  const d = {}
  if (prev.w !== next.w) d.w = `${toW(prev.w)}→${toW(next.w)}`
  if (prev.u !== next.u) d.u = `${toU(prev.u)}→${toU(next.u)}`
  if (next.u > 0) {
    const ah = typeof prev.h === 'number' ? prev.h : undefined
    const bh = typeof next.h === 'number' ? next.h : undefined
    if (ah !== bh) d.h = bh
  }
  if (prev.c !== next.c) d.c = `${prev.c}→${next.c}`
  return d
}
function toW(w) { return w === 0 ? '晴' : w === 1 ? '曇' : '雨' }
function toU(u) { return u === 1 ? '曇へ' : u === 2 ? '雨へ' : u === 3 ? '晴へ' : '変化なし' }

// === ライフサイクル ===
function toggleSpotList() {
  isSpotListVisible.value = !isSpotListVisible.value
}

onMounted(() => {
  // プラン未取得ならプラン作成に戻す
  if (!navStore.plan) {
    router.push('/plan')
    return
  }
  // 周遊順でポーリング開始
  rt.startPolling(plan.value.waypoints_info)
})

onUnmounted(() => {
  rt.stopPolling()
})
</script>

<style scoped>
.nav-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 100%;
}

.loading-overlay {
  padding: 24px;
  text-align: center;
  color: #333;
}

.nav-container {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 12px;
}

.map-wrapper {
  position: relative;
  min-height: 60vh;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

/* 右パネル */
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.spot-list-toggle {
  background: #0ea5e9;
  color: white;
  border: none;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
}
.spot-list-toggle:hover {
  background: #0284c7;
}

.spot-list, .poi-list {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
}
.spot-list h3, .poi-list h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #374151;
}

.spot-ol {
  list-style: none;
  margin: 0;
  padding: 0;
}
.spot-li + .spot-li {
  margin-top: 8px;
}
.spot-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.order-index {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: white;
  background: #9ca3af;
  border-radius: 50%;
}
.spot-name {
  font-size: 14px;
  color: #111827;
  font-weight: 600;
}

/* RT最新表示 */
.rt-latest {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.rt-empty .rt-muted {
  color: #9ca3af;
  font-size: 12px;
}
.rt-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 12px;
  background: #f3f4f6;
  color: #374151;
}
.rt-upcoming {
  background: #fff7ed;
  color: #9a3412;
}
.rt-cong {
  background: #eef2ff;
  color: #3730a3;
}

/* トースト通知 */
.toast-stack {
  position: fixed;
  right: 16px;
  top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 9999;
}
.toast {
  min-width: 260px;
  max-width: 360px;
  background: #111827;
  color: #f9fafb;
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 10px 20px rgba(0,0,0,0.2);
  cursor: pointer;
}
.toast-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 4px;
}
.toast-body {
  font-size: 13px;
  opacity: 0.95;
}
.toast-diff {
  margin-top: 2px;
  font-size: 12px;
  opacity: 0.9;
}

/* エラー表示 */
.error-view {
  padding: 20px;
  text-align: center;
}
</style>
