<template>
  <div class="nav-view">
    <div
      v-if="isDebug"
      style="
        position: fixed;
        bottom: 10px;
        right: 10px;
        z-index: 9999;
        background: white;
        padding: 10px;
        border: 1px solid #ccc;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
      "
    >
      <h4>デバッグ用パネル</h4>
      <div style="display: flex; gap: 6px; margin-bottom: 6px">
        <input v-model.number="debugLat" type="number" step="0.000001" placeholder="lat" style="width: 120px" />
        <input v-model.number="debugLng" type="number" step="0.000001" placeholder="lng" style="width: 120px" />
        <button @click="setDebugPos(debugLat, debugLng)" style="padding: 6px 10px">
          現在地をセット
        </button>
        <label style="font-size: 12px; display: flex; align-items: center; gap: 4px; margin-left: 6px">
          <input type="checkbox" v-model="following" @change="toggleFollowing" />
          追従
        </label>
      </div>
      <p style="margin: 0; font-size: 12px; color: #333">
        現在地:
        <span v-if="currentPos">{{ currentPos.lat.toFixed(4) }}, {{ currentPos.lng.toFixed(4) }}</span>
        <span v-else>未取得</span>
      </p>
    </div>

    <div v-if="isRouteReady" class="nav-container">
      <div class="map-wrapper">
        <NavMap ref="navMap" :plan="plan" :current-pos="currentPos" />
        <div class="map-actions">
          <button
            type="button"
            class="map-action-btn"
            :disabled="!currentPos"
            @click="recenterOnCurrent"
          >
            現在地へ
          </button>
          <button
            type="button"
            class="map-action-btn"
            :class="{ 'map-action-btn--active': following }"
            @click="toggleFollowMode"
          >
            {{ following ? '追従中' : '追従OFF' }}
          </button>
        </div>
      </div>

      <div class="controls">
        <div v-if="!isNavigationReady" class="start-nav-panel">
          <button @click="startGuidance" :disabled="isNavigating" class="start-nav-button">
            {{ isNavigating ? '案内を生成中...' : 'ナビゲーションを開始' }}
          </button>
          <div v-if="navError" class="error-box">
            エラー: {{ navError }}
          </div>
        </div>
        
        <div v-if="isNavigationReady">
          <div class="conn-panel">
            <div class="conn-row">
              <span :class="['chip', online ? 'ok' : 'warn']">{{
                online ? 'オンライン' : 'オフライン'
              }}</span>
              <span v-if="isLoraConnected" class="chip ok">LoRa接続済み</span>
              <span v-else-if="isLoraConnecting" class="chip busy">LoRa接続中...</span>
              <span v-else class="chip muted">LoRa未接続</span>
              <button
                v-if="!isLoraConnected"
                @click="connectLoraDevice"
                :disabled="isLoraConnecting"
                class="join-btn"
              >
                LoRaデバイスに接続
              </button>
              <button v-else @click="disconnectLoraDevice" class="join-btn">切断</button>
            </div>
            <div class="conn-row">
              <span class="chip" :class="isPollingEnabled ? 'ok' : 'muted'">
                リアルタイム取得: {{ isPollingEnabled ? 'ON' : 'OFF' }}
              </span>
              <button class="join-btn" @click="togglePolling">
                {{ isPollingEnabled ? '停止' : '開始' }}
              </button>
            </div>
          </div>
          <button @click="toggleSpotList" class="spot-list-toggle">
            {{ isSpotListVisible ? 'リストを隠す' : 'スポット一覧' }}
          </button>
        </div>

        <div v-if="isSpotListVisible" class="spot-list">
          <h3>周遊スポット</h3>
          <ul>
            <li v-for="(poi, index) in sortedWaypoints" :key="poi.spot_id">
              <button @click="focusOnSpot(poi)">
                <span class="order-index">{{ index + 1 }}</span>
                {{ poi.name }}
                <span class="rt-badges" v-if="isNavigationReady && latestBySpot(poi.spot_id)">
                  <span
                    class="rt-badge weather"
                    :title="weatherTitle(latestBySpot(poi.spot_id))"
                  >
                    {{ weatherEmoji(latestBySpot(poi.spot_id)?.w) }}
                  </span>
                  <span
                    v-if="latestBySpot(poi.spot_id)?.u > 0"
                    class="rt-badge upcoming"
                    :title="upcomingTitle(latestBySpot(poi.spot_id))"
                  >
                    {{ upcomingEmoji(latestBySpot(poi.spot_id)?.u) }}
                    <small v-if="typeof latestBySpot(poi.spot_id)?.h === 'number'"
                      >{{ latestBySpot(poi.spot_id)?.h }}h</small
                    >
                  </span>
                  <span class="rt-badge crowd" :title="crowdTitle(latestBySpot(poi.spot_id))">
                    {{ crowdBar(latestBySpot(poi.spot_id)?.c) }}
                  </span>
                </span>
              </button>
            </li>
          </ul>

          <div v-if="isNavigationReady && sortedAlongPois.length > 0" class="nearby-section">
            <h3 class="nearby-title">周辺のスポット</h3>
            <ul>
              <li v-for="poi in sortedAlongPois" :key="poi.spot_id">
                <button @click="focusOnSpot(poi)" class="nearby-button">
                  {{ poi.name }}
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div class="toast-stack">
        <div v-for="t in toasts" :key="t.id" class="toast" role="status" aria-live="polite">
          <strong>{{ t.title }}</strong>
          <div class="toast-body">{{ t.body }}</div>
        </div>
      </div>
    </div>

    <div v-else class="error-view">
      <p v-if="navError">エラーが発生しました: {{ navError }}</p>
      <p v-else>ナビゲーションプランが見つかりません。</p>
      <router-link to="/plan">プラン作成画面に戻る</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useNavStore } from '@/stores/nav'
import { useRouter } from 'vue-router'
import NavMap from '@/components/NavMap.vue'
import { useRtStore } from '@/stores/rt'
import {
  connect,
  join,
  send,
  disconnect,
  getIsJoined
} from '@/lib/loraBridge'

import { enqueueAudio, resetPlaybackState } from '@/lib/audioManager.js'
import * as geo from '@/lib/geoutils.js'
import { tilesForRoute } from '@/lib/tiles'

import { usePosition } from '@/lib/usePosition.mock.js'
// import { usePosition } from '@/lib/usePosition.js';

const navStore = useNavStore()
const rtStore = useRtStore()
const router = useRouter()

const {
  plan,
  isRouteReady,
  isNavigating,
  isNavigationReady,
  error: navError,
} = storeToRefs(navStore)

const navMap = ref(null)
const isSpotListVisible = ref(true)
const online = ref(navigator.onLine)
const isLoraConnecting = ref(false)
const isLoraConnected = ref(false)
let loraSendInterval = null
const {
  currentPos,
  debugLat,
  debugLng,
  following,
  setDebugPos,
  toggleFollowing,
  isMock
} = usePosition()
const isDebug = computed(() => !!isMock)
const isPollingEnabled = ref(false)
const didPrecacheTiles = ref(false)

const recenterOnCurrent = () => {
  if (!navMap.value || !currentPos.value) return
  navMap.value.flyToSpot(currentPos.value.lat, currentPos.value.lng)
}

const toggleFollowMode = () => {
  toggleFollowing()
  if (following.value) {
    recenterOnCurrent()
  }
}


// --- ★★★ 新しいアクションを呼び出すメソッド ★★★ ---
const startGuidance = async () => {
  resetPlaybackState()
  await navStore.startGuidance()
}
// --- ★★★ ここまで ★★★ ---

const handleSwMessage = (event) => {
  const data = event.data
  if (data?.type === 'PRECACHE_TILES_RESULT' && data.summary) {
    const { added, skipped, failed } = data.summary
    console.debug('[sw] precache tiles result', data.summary)
    if (failed > 0) {
      pushToast('地図キャッシュ', `一部タイルの取得に失敗しました (${failed})`, 5000)
    } else if (added > 0) {
      pushToast('地図キャッシュ', `タイル ${added} 件を保存しました`, 3000)
    }
  }
}

onMounted(() => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', handleSwMessage)
  }

  // ★★★ isRouteReadyをチェックするように修正 ★★★
  if (!isRouteReady.value) {
    router.push('/plan')
    return
  }
})

onUnmounted(() => {
  rtStore.stopPolling()
  stopLoraPolling()
  resetPlaybackState()
  if (isLoraConnected.value) {
    disconnectLoraDevice()
  }
  window.removeEventListener('online', _updateOnline)
  window.removeEventListener('offline', _updateOnline)
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.removeEventListener('message', handleSwMessage)
  }
})

watch(
  () => plan.value?.polyline,
  (polyline) => {
    if (!polyline || polyline.length === 0) {
      didPrecacheTiles.value = false
      return
    }
    if (didPrecacheTiles.value) return
    requestTilePrecache(polyline)
  },
  { immediate: true }
)

async function requestTilePrecache(polyline) {
  if (!('serviceWorker' in navigator)) return
  const candidateTiles = tilesForRoute(polyline, { zooms: [12, 13, 14, 15], marginDeg: 0.03, maxTiles: 800 })
  if (!candidateTiles.length) return

  const payload = {
    type: 'PRECACHE_TILES',
    tiles: candidateTiles,
    meta: {
      requestedAt: Date.now(),
      planCreatedAt: plan.value?.createdAt ?? null,
    }
  }

  const postToController = (controller) => {
    if (!controller) return false
    try {
      controller.postMessage(payload)
      didPrecacheTiles.value = true
      return true
    } catch (err) {
      console.warn('[sw] failed to post precache message', err)
      return false
    }
  }

  if (postToController(navigator.serviceWorker.controller)) return

  try {
    const registration = await navigator.serviceWorker.ready
    if (postToController(registration.active)) return
  } catch (err) {
    console.warn('[sw] service worker ready wait failed', err)
  }
}


// マップ上の現在位置マーカーを更新
watch(currentPos, (newPos) => {
  if (navMap.value && newPos) {
    navMap.value.updateCurrentPosition(newPos.lat, newPos.lng)
    if (following.value) {
      navMap.value.flyToSpot(newPos.lat, newPos.lng)
    }
  }
})

watch(following, (isOn) => {
  if (isOn) {
    recenterOnCurrent()
  }
})

watch(
  () => plan.value?.waypoints_info,
  (waypoints) => {
    if (!Array.isArray(waypoints) || waypoints.length === 0) {
      rtStore.setSpotOrder([])
      if (isPollingEnabled.value) {
        stopAllRtPolling()
      }
      return
    }
    rtStore.setSpotOrder(waypoints)
    if (isPollingEnabled.value) {
      startRtPollingIfNeeded()
    }
  },
  { immediate: true }
)

watch(isNavigationReady, (ready) => {
  if (!ready) {
    stopAllRtPolling()
    isPollingEnabled.value = false
    return
  }
  if (!isPollingEnabled.value) {
    isPollingEnabled.value = true
  }
  startRtPollingIfNeeded()
})

// スポット接近時の通常案内をキューに追加するロジック
watch(currentPos, (newPos) => {
  // ★★★ isNavigationReadyをチェックする条件を追加 ★★★
  if (!isNavigationReady.value || !plan.value || !newPos) return;

  const allSpots = [
    ...(plan.value?.waypoints_info || []),
    ...(plan.value?.along_pois || [])
  ];
  if (allSpots.length === 0) return;

  const travelMode = geo.getCurrentTravelMode(newPos, plan.value?.segments ?? plan.value?.route);
  const bufferM = (travelMode === 'car') ? 350 : 15;

  allSpots.forEach((spot) => {
    if (!spot.lat || !spot.lon) return;
    const distance = geo.calculateDistance(newPos, { lat: spot.lat, lng: spot.lon });

    if (distance <= bufferM) {
      const assetsArray = Array.isArray(plan.value.assets)
        ? plan.value.assets
        : Object.values(plan.value.assets || {});
      
      const asset = assetsArray.find(a => a.spot_id === spot.spot_id && !a.situation);

      const voiceUrl = asset?.audio?.url || asset?.audio_url
      if (voiceUrl) {
        enqueueAudio({
          id: spot.spot_id,
          name: spot.name,
          voice_path: voiceUrl
        });
      }
    }
  });
});

// LoRa受信データをトリガーに状況別案内をキューに追加するロジック
watch(
  () => rtStore.notifyLog.length,
  (newLength, oldLength) => {
    // ★★★ isNavigationReadyをチェックする条件を追加 ★★★
    if (newLength <= oldLength || !isNavigationReady.value || !plan.value) return;

    const event = rtStore.notifyLog[newLength - 1];
    const spotId = event.spot_id;
    const spotName = spotNameMap.value.get(spotId) || spotId;
    const assets = Array.isArray(plan.value?.assets)
      ? plan.value.assets
      : Object.values(plan.value.assets || {});

    const weatherChanged = !event.prev || event.prev.w !== event.next.w;
    if (weatherChanged && (event.next.w === 1 || event.next.w === 2)) {
      const situationType = `weather_${event.next.w}`;
      const asset = assets.find(a => a.spot_id === spotId && a.situation === situationType);
      const voiceUrl = asset?.audio?.url || asset?.audio_url
      if (voiceUrl) {
        enqueueAudio({
          id: `${spotId}_${situationType}`,
          name: `${spotName} (天気案内)`,
          voice_path: voiceUrl
        });
      }
    }

    const congestionChanged = !event.prev || event.prev.c !== event.next.c;
    if (congestionChanged && (event.next.c === 1 || event.next.c === 2)) {
      const situationType = `congestion_${event.next.c}`;
      const asset = assets.find(a => a.spot_id === spotId && a.situation === situationType);
      const voiceUrl = asset?.audio?.url || asset?.audio_url
      if (voiceUrl) {
        enqueueAudio({
          id: `${spotId}_${situationType}`,
          name: `${spotName} (混雑度案内)`,
          voice_path: voiceUrl
        });
      }
    }
  }
);


// --- 以下、既存のロジック (UI、LoRa接続、ライフサイクルなど) ---
// (※ ユーザー提供のコードから変更なし)
const sortedWaypoints = computed(() => {
  if (plan.value && plan.value.waypoints_info) {
    return [...plan.value.waypoints_info].sort(
      (a, b) => (a.nearest_idx || 0) - (b.nearest_idx || 0)
    )
  }
  return []
})

const sortedAlongPois = computed(() => {
  if (plan.value && plan.value.along_pois) {
    return [...plan.value.along_pois].sort(
      (a, b) => (a.order_index ?? a.nearest_idx ?? 0) - (b.order_index ?? b.nearest_idx ?? 0)
    )
  }
  return []
})

const spotNameMap = computed(() => {
  const m = new Map()
  if (plan.value?.waypoints_info) {
    for (const wp of plan.value.waypoints_info) {
      if (wp.spot_id) m.set(wp.spot_id, wp.name || wp.spot_id)
    }
  }
  if (plan.value?.along_pois) {
    for (const p of plan.value.along_pois) {
      if (p.spot_id && !m.has(p.spot_id)) m.set(p.spot_id, p.name || p.spot_id)
    }
  }
  return m
})

const toasts = ref([])
function pushToast(title, body, timeoutMs = 4000) {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  toasts.value.push({ id, title, body })
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }, timeoutMs)
}

function startLoraPolling() {
  stopLoraPolling()
  const spots = sortedWaypoints.value
  if (spots.length === 0 || !isLoraConnected.value) return
  let currentIndex = 0
  const loraTask = async () => {
    if (!getIsJoined()) {
      console.warn('[LoRa Polling] Not joined. Re-joining...')
      isLoraConnected.value = false
      isLoraConnecting.value = true
      try {
        await join()
        isLoraConnected.value = true
      } catch (e) {
        pushToast('LoRa Error', 'Failed to re-join.', 6000)
        await disconnectLoraDevice()
        return
      } finally {
        isLoraConnecting.value = false
      }
    }
    const spotId = spots[currentIndex].spot_id
    await send(spotId)
    currentIndex = (currentIndex + 1) % spots.length
  }
  loraTask()
  loraSendInterval = setInterval(loraTask, 60000)
}

function stopLoraPolling() {
  if (loraSendInterval) {
    clearInterval(loraSendInterval)
    loraSendInterval = null
  }
}

async function connectLoraDevice() {
  isLoraConnecting.value = true
  try {
    await connect(
      (receivedData) => rtStore.processRtDoc(receivedData),
      () => {
        pushToast('LoRa', 'Device disconnected.', 5000)
        disconnectLoraDevice()
      }
    )
    await join()
    isLoraConnected.value = true
    pushToast('LoRa', 'Connected to device and joined network.')
    await new Promise((resolve) => setTimeout(resolve, 3000))
    if (isPollingEnabled.value) {
      rtStore.stopPolling()
      startLoraPolling()
    }
  } catch (error) {
    alert(`LoRa connection error: ${error.message}`)
    await disconnect()
    isLoraConnected.value = false
  } finally {
    isLoraConnecting.value = false
  }
}

async function disconnectLoraDevice() {
  stopLoraPolling()
  await disconnect()
  isLoraConnected.value = false
  if (online.value && isPollingEnabled.value) {
    rtStore.startPolling(plan.value?.waypoints_info || [])
  } else {
    rtStore.stopPolling()
  }
}

function _updateOnline() { online.value = navigator.onLine }
window.addEventListener('online', _updateOnline)
window.addEventListener('offline', _updateOnline)

watch(online, (isOnline) => {
  if (!isPollingEnabled.value) {
    rtStore.stopPolling()
    return
  }
  if (isOnline && !isLoraConnected.value) {
    rtStore.startPolling(plan.value?.waypoints_info || [])
  } else if (!isOnline) {
    rtStore.stopPolling()
  }
})

function startRtPollingIfNeeded() {
  if (!isPollingEnabled.value) return
  if (isLoraConnected.value) {
    rtStore.stopPolling()
    startLoraPolling()
  } else if (online.value) {
    stopLoraPolling()
    rtStore.startPolling(plan.value?.waypoints_info || [])
  } else {
    pushToast('リアルタイム', 'オフラインのためHTTP取得不可。LoRa接続すると取得できます。', 5000)
  }
}

function stopAllRtPolling() {
  stopLoraPolling()
  rtStore.stopPolling()
}

function togglePolling() {
  isPollingEnabled.value = !isPollingEnabled.value
  if (isPollingEnabled.value) startRtPollingIfNeeded()
  else stopAllRtPolling()
}


function toggleSpotList() { isSpotListVisible.value = !isSpotListVisible.value }
function focusOnSpot(poi) { if (navMap.value) { navMap.value.flyToSpot(poi.lat, poi.lon) } }
function weatherEmoji(w) { return { 0: '☀', 1: '☁', 2: '☂' }[w] || '▫' }
function upcomingEmoji(u) { return { 1: '↗☁', 2: '↗☔', 3: '↗☀' }[u] || '' }
function weatherTitle(doc) { if (!doc) return ''; const m = { 0: '晴れ', 1: '曇り', 2: '雨' }; return `現在: ${m[doc.w] ?? '-'}` }
function upcomingTitle(doc) { if (!doc || !doc.u) return ''; const m = { 1: '曇り', 2: '雨', 3: '晴れ' }; const h = typeof doc.h === 'number' ? `${doc.h}時間後` : ''; return `${h}${m[doc.u] ?? ''}に変化` }
function crowdBar(c) { const n = Number.isFinite(c) ? Math.max(0, Math.min(2, c)) : 0; return '●'.repeat(n + 1) + '○'.repeat(2 - n) }
function crowdTitle(doc) { if (!doc) return ''; const l = ['空', 'やや混雑', '混雑']; const c = Math.max(0, Math.min(2, Number(doc.c ?? 0))); return `混雑: ${l[c]}` }
function latestBySpot(spotId) { return rtStore.getLatest?.(spotId) ?? null }

watch(
  () => rtStore.notifyLog.length,
  (len, prev) => {
    if (len <= prev) return
    const ev = rtStore.notifyLog[len - 1]
    const name = spotNameMap.value.get(ev.spot_id) || ev.spot_id
    const diffs = []
    if (!ev.prev || ev.prev.w !== ev.next.w) {
      const m = { 0: '晴れ', 1: '曇り', 2: '雨' }
      diffs.push(`天気: ${m[ev.next.w] ?? '-'}`)
    }
    if (!ev.prev || ev.prev.c !== ev.next.c) {
      const l = ['空', 'やや混雑', '混雑']
      diffs.push(`混雑: ${l[ev.next.c]}`)
    }
    const body = diffs.join(' / ')
    if (body) {
      pushToast(name, body)
    }
  }
)
</script>

<style scoped>
/* スタイルは変更ありません */
.nav-view {
  position: relative;
  width: 100%;
  height: 100vh;
}
.loading-overlay { /* ★★★ 既存のローディングは削除 (ストアのローディングフラグを使うため) ★★★ */
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  font-size: 1.2rem;
}
.nav-container {
  position: relative;
  width: 100%;
  height: 100%;
}
.map-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.map-actions {
  position: absolute;
  right: 16px;
  bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 900;
}

.map-action-btn {
  min-width: 100px;
  padding: 10px 14px;
  border-radius: 8px;
  border: none;
  background: rgba(15, 23, 42, 0.82);
  color: #f8fafc;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.24);
  transition: background-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.map-action-btn:hover {
  background: rgba(37, 99, 235, 0.9);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.28);
}

.map-action-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.map-action-btn--active {
  background: rgba(16, 185, 129, 0.92);
}
.controls {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  max-height: calc(100vh - 20px);
}

/* ★★★ 「ナビ開始」ボタン用のスタイルを追加 ★★★ */
.start-nav-panel {
  background: #ffffff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  margin-bottom: 10px;
  width: 250px;
}
.start-nav-button {
  width: 100%;
  padding: 12px;
  font-size: 1rem;
  font-weight: bold;
  background: #1d4ed8;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}
.start-nav-button:hover {
  background: #2563eb;
}
.start-nav-button:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
.error-box {
  background: #fef2f2;
  color: #b91c1c;
  padding: 8px;
  border-radius: 4px;
  margin-top: 8px;
  font-size: 0.9rem;
}
/* ★★★ ここまで ★★★ */


.conn-panel {
  background: #ffffff;
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  margin-bottom: 10px;
  min-width: 250px;
}
.conn-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.chip {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
}
.chip.ok { background: #e6ffec; color: #137333; }
.chip.warn { background: #fff4e5; color: #8a5a00; }
.chip.busy { background: #e7f0ff; color: #0b57d0; }
.chip.muted { background: #eee; color: #666; }
.join-btn {
  padding: 6px 10px;
  font-size: 0.9rem;
  background: #0b57d0;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  margin-left: auto;
}
.join-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.spot-list-toggle {
  padding: 10px 15px;
  font-size: 1rem;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  margin-bottom: 10px;
}
.spot-list {
  background: white;
  border-radius: 5px;
  padding: 10px;
  max-height: 75vh;
  overflow-y: auto;
  min-width: 250px;
}
.spot-list h3 {
  margin-top: 0;
  margin-bottom: 10px;
}
.spot-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.spot-list li button {
  width: 100%;
  padding: 8px 12px;
  text-align: left;
  background: none;
  border: none;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  display: flex;
  align-items: center;
}
.spot-list li:last-child button { border-bottom: none; }
.spot-list li button:hover { background-color: #f5f5f5; }
.order-index {
  display: inline-block;
  width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  border-radius: 50%;
  background-color: #007bff;
  color: white;
  font-weight: bold;
  margin-right: 10px;
}
.rt-badges { margin-left: auto; }
.toast-stack {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 1100;
}
.toast {
  background: rgba(30, 30, 30, 0.95);
  color: #fff;
  padding: 10px 12px;
  border-radius: 8px;
}
.error-view {
  padding: 20px;
  text-align: center;
}
</style>
