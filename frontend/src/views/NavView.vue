<template>
  <div class="nav-view">
    <div v-if="navStore.isLoading" class="loading-overlay">
      <p>案内プランを生成中です...</p>
    </div>
    
    <div v-else-if="plan && plan.waypoints_info" class="nav-container">
      <div class="map-wrapper">
        <NavMap ref="navMap" :plan="plan" />
      </div>
      <div class="controls">

        <div class="conn-panel">
          <div class="conn-row">
            <span :class="['chip', online ? 'ok' : 'warn']">{{ online ? 'オンライン' : 'オフライン' }}</span>
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
            <button v-else @click="disconnectLoraDevice" class="join-btn">
              切断
            </button>
          </div>
        </div>

        <button @click="toggleSpotList" class="spot-list-toggle">
          {{ isSpotListVisible ? 'リストを隠す' : 'スポット一覧' }}
        </button>
        
        <div v-if="isSpotListVisible" class="spot-list">
          
          <h3>周遊スポット</h3>
          <ul>
            <li v-for="(poi, index) in sortedWaypoints" :key="poi.spot_id">
              <button @click="focusOnSpot(poi)">
                <span class="order-index">{{ index + 1 }}</span>
                {{ poi.name }}
                <span class="rt-badges" v-if="latestBySpot(poi.spot_id)">
                  <span class="rt-badge weather" :title="weatherTitle(latestBySpot(poi.spot_id))">
                    {{ weatherEmoji(latestBySpot(poi.spot_id)?.w) }}
                  </span>
                  <span
                    v-if="latestBySpot(poi.spot_id)?.u > 0"
                    class="rt-badge upcoming"
                    :title="upcomingTitle(latestBySpot(poi.spot_id))"
                  >
                    {{ upcomingEmoji(latestBySpot(poi.spot_id)?.u) }}
                    <small v-if="typeof latestBySpot(poi.spot_id)?.h === 'number'">{{ latestBySpot(poi.spot_id)?.h }}h</small>
                  </span>
                  <span class="rt-badge crowd" :title="crowdTitle(latestBySpot(poi.spot_id))">
                    {{ crowdBar(latestBySpot(poi.spot_id)?.c) }}
                  </span>
                </span>
              </button>
            </li>
          </ul>

          <div v-if="sortedAlongPois.length > 0" class="nearby-section">
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
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast"
          role="status"
          aria-live="polite"
        >
          <strong>{{ t.title }}</strong>
          <div class="toast-body">{{ t.body }}</div>
        </div>
      </div>

    </div>
    
    <div v-else class="error-view">
      <p>ナビゲーションプランが見つかりません。</p>
      <router-link to="/plan">プラン作成画面に戻る</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useNavStore } from '@/stores/nav';
import { useRouter } from 'vue-router';
import NavMap from '@/components/NavMap.vue';
import { useRtStore } from '@/stores/rt';
import { connect, join, send, startReceiveLoop, disconnect, getIsJoined } from '@/lib/loraBridge';

const navStore = useNavStore();
const rtStore = useRtStore();
const router = useRouter();
const plan = computed(() => navStore.plan);
const navMap = ref(null);
const isSpotListVisible = ref(true);

const online = ref(navigator.onLine);
const prefetchDone = ref(false);

const isLoraConnecting = ref(false);
const isLoraConnected = ref(false);
let loraSendInterval = null;


function _updateOnline() { online.value = navigator.onLine; }
window.addEventListener('online', _updateOnline);
window.addEventListener('offline', _updateOnline);

const sortedWaypoints = computed(() => {
  if (plan.value && plan.value.waypoints_info) {
    return [...plan.value.waypoints_info].sort((a, b) => (a.nearest_idx || 0) - (b.nearest_idx || 0));
  }
  return [];
});

const sortedAlongPois = computed(() => {
  if (plan.value && plan.value.along_pois) {
    return [...plan.value.along_pois].sort((a, b) => (a.order_index ?? a.nearest_idx ?? 0) - (b.order_index ?? b.nearest_idx ?? 0));
  }
  return [];
});

const spotNameMap = computed(() => {
  const m = new Map();
  if (plan.value?.waypoints_info) {
    for (const wp of plan.value.waypoints_info) {
      if (wp.spot_id) m.set(wp.spot_id, wp.name || wp.spot_id);
    }
  }
  if (plan.value?.along_pois) {
    for (const p of plan.value.along_pois) {
      if (p.spot_id && !m.has(p.spot_id)) m.set(p.spot_id, p.name || p.spot_id);
    }
  }
  return m;
});

const toasts = ref([]);
function pushToast(title, body, timeoutMs = 4000) {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  toasts.value.push({ id, title, body });
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id);
  }, timeoutMs);
}

async function checkPrefetchDone() {
  try {
    if (!plan.value?.pack_id || !Array.isArray(plan.value?.assets)) return false;
    if (!('caches' in window)) return false;
    const cacheName = `packs-${plan.value.pack_id}`;
    const cache = await caches.open(cacheName);
    const urls = plan.value.assets.map(a => a?.audio?.url).filter(Boolean);
    if (urls.length === 0) return false;
    const results = await Promise.all(urls.map(u => cache.match(u)));
    return results.every(r => !!r);
  } catch {
    return false;
  }
}
let _prefetchPollId = null;
async function startPrefetchWatcher() {
  const ok = await checkPrefetchDone();
  if (ok) {
    prefetchDone.value = true;
    return;
  }
  _prefetchPollId = window.setInterval(async () => {
    const ready = await checkPrefetchDone();
    if (ready) {
      prefetchDone.value = true;
      stopPrefetchWatcher();
    }
  }, 5000);
}
function stopPrefetchWatcher() {
  if (_prefetchPollId) {
    clearInterval(_prefetchPollId);
    _prefetchPollId = null;
  }
}

function startLoraPolling() {
  stopLoraPolling();
  const spots = sortedWaypoints.value;
  if (spots.length === 0 || !isLoraConnected.value) return;
  
  let currentIndex = 0;
  
  // 毎分実行するタスク
  const loraTask = async () => {
    // 内部フラグをチェックするだけなので、処理が非常に高速
    if (!getIsJoined()) {
      console.warn('[LoRa Polling] ネットワークから切断されています。再接続を試みます...');
      // UIの状態を「接続中」に戻し、再Join処理を試みる
      isLoraConnected.value = false;
      isLoraConnecting.value = true;
      try {
        await join();
        console.log('[LoRa Polling] 再Joinに成功しました。');
        isLoraConnected.value = true;
      } catch (e) {
        console.error('[LoRa Polling] 再Joinに失敗しました。ポーリングを停止します。', e);
        pushToast('LoRa接続エラー', 'ネットワークへの再接続に失敗しました。', 6000);
        await disconnectLoraDevice(); // 完全に失敗した場合は切断処理へ
        return;
      } finally {
        isLoraConnecting.value = false;
      }
    }
    
    // データを送信
    const spotId = spots[currentIndex].spot_id;
    // const spotId = "a"; // ★ テスト用に1文字だけ送信する
    console.log(`[LoRa] ${spotId}の情報をリクエストします。`);
    await send(spotId);
    
    currentIndex = (currentIndex + 1) % spots.length;
  };
  
  // すぐに一回実行し、その後タイマーを設定
  loraTask();
  loraSendInterval = setInterval(loraTask, 60000);
}

function stopLoraPolling() {
  if (loraSendInterval) {
    clearInterval(loraSendInterval);
    loraSendInterval = null;
    console.log('[LoRa] ポーリングを停止しました。');
  }
}

async function connectLoraDevice() {
  isLoraConnecting.value = true;
  try {
    // データ受信と切断イベントのコールバックを渡す
    const portConnected = await connect(
      (receivedData) => { // onData
        console.log('LoRa経由でデータを受信:', receivedData);
        if (receivedData && receivedData.s) {
          rtStore.lastBySpot[receivedData.s] = receivedData;
        }
      },
      () => { // onDisconnect
        pushToast('LoRa', 'デバイスとの接続が切れました。', 5000);
        disconnectLoraDevice();
      }
    );

    if (!portConnected) {
      alert('シリアルポートに接続できませんでした。');
      isLoraConnecting.value = false;
      return;
    }
    
    const joined = await join();
    if (!joined) {
        // join Promiseがrejectされた場合（join関数内でalertは不要）
        alert('LoRaWANネットワークに参加できませんでした。');
        await disconnect();
        isLoraConnecting.value = false;
        return;
    }
    
    isLoraConnected.value = true;
    pushToast('LoRa', 'デバイスに接続し、ネットワークに参加しました。');

    console.log('Join成功。デバイス安定化のため3秒待機します...');
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    console.log('LoRa接続成功。HTTPポーリングを停止し、LoRaポーリングを開始します。');
    rtStore.stopPolling();
    startLoraPolling();

  } catch (error) {
    console.error("LoRa接続処理中にエラー:", error);
    alert(`LoRa接続処理中にエラーが発生しました: ${error.message}`);
    await disconnect();
    isLoraConnected.value = false;
  } finally {
    isLoraConnecting.value = false;
  }
}


async function disconnectLoraDevice() {
  stopLoraPolling();
  await disconnect();
  isLoraConnected.value = false;
  isLoraConnecting.value = false; // 念のため
  console.log("LoRaデバイスから切断しました。");

  // オンラインならHTTPポーリングを再開
  if (online.value) {
    console.log('LoRa切断。オンラインのためHTTPポーリングを再開します。');
    rtStore.startPolling(plan.value?.waypoints_info || []);
  }
}

watch(online, (isOnline) => {
  if (isOnline) {
    console.log('オンラインに復帰しました。');
    // LoRaが接続されていなければ、HTTPポーリングを開始
    if (!isLoraConnected.value) {
      console.log('HTTPポーリングを開始します。');
      stopLoraPolling();
      rtStore.startPolling(plan.value?.waypoints_info || []);
    }
  } else {
    console.log('オフラインになりました。');
    // オンライン状態に関わらずLoRa接続中ならLoRaポーリングを継続するので、
    // ここではHTTPポーリングの停止のみ行う
    console.log('HTTPポーリングを停止します。');
    rtStore.stopPolling();
  }
});

onMounted(() => {
  if (!navStore.plan) {
    router.push('/plan');
    return;
  }
  startPrefetchWatcher();

  // 初期状態では常にHTTPポーリングを開始する（LoRa接続時に切り替える）
  rtStore.startPolling(plan.value?.waypoints_info || []);
});

onUnmounted(() => {
  rtStore.stopPolling();
  stopLoraPolling();
  stopPrefetchWatcher();
  if (isLoraConnected.value) {
    disconnectLoraDevice();
  }
  window.removeEventListener('online', _updateOnline);
  window.removeEventListener('offline', _updateOnline);
});

function toggleSpotList() {
  isSpotListVisible.value = !isSpotListVisible.value;
}

function focusOnSpot(poi) {
  if (navMap.value) {
    navMap.value.flyToSpot(poi.lat, poi.lon);
  }
}

function weatherEmoji(w) {
  if (w === 0) return '☀';
  if (w === 1) return '☁';
  if (w === 2) return '☂';
  return '▫';
}
function upcomingEmoji(u) {
  if (u === 1) return '↗☁';
  if (u === 2) return '↗☔';
  if (u === 3) return '↗☀';
  return '';
}
function weatherTitle(doc) {
  if (!doc) return '';
  const nowMap = { 0: '晴れ', 1: '曇り', 2: '雨' };
  return `現在: ${nowMap[doc.w] ?? '-'}`;
}
function upcomingTitle(doc) {
  if (!doc || !doc.u || doc.u === 0) return '';
  const toMap = { 1: '曇りに', 2: '雨に', 3: '晴れに' };
  const h = typeof doc.h === 'number' ? `${doc.h}時間後` : '';
  return `${h}${toMap[doc.u] ?? ''}変化`;
}
function crowdBar(c) {
  const n = Number.isFinite(c) ? Math.max(0, Math.min(4, c)) : 0
  return '○'.repeat(4 - n) + '●'.repeat(n + 1 - 1)
}
function crowdTitle(doc) {
  if (!doc) return '';
  const labels = ['とても空いている', 'やや空き', 'ふつう', 'やや混雑', 'とても混雑'];
  const c = Math.max(0, Math.min(4, Number(doc.c ?? 0)));
  return `混雑: ${labels[c]}`;
}
function latestBySpot(spotId) {
  return rtStore.getLatest?.(spotId) ?? null;
}

watch(
  () => rtStore.notifyLog.length,
  (len, prev) => {
    if (len <= prev) return;
    const ev = rtStore.notifyLog[len - 1];
    const name = spotNameMap.value.get(ev.spot_id) || ev.spot_id;

    const diffs = [];
    if (!ev.prev || ev.prev.w !== ev.next.w) {
      const nowMap = { 0: '晴れ', 1: '曇り', 2: '雨' };
      diffs.push(`現在天気: ${ev.prev ? (nowMap[ev.prev.w] ?? '-') + '→' : ''}${nowMap[ev.next.w] ?? '-'}`);
    }
    if (!ev.prev || ev.prev.u !== ev.next.u || (ev.next.u > 0 && ev.prev?.h !== ev.next.h)) {
      if (ev.next.u > 0) {
        const toMap = { 1: '曇り', 2: '雨', 3: '晴れ' };
        const htxt = typeof ev.next.h === 'number' ? `${ev.next.h}時間後` : '近く';
        diffs.push(`${htxt}に${toMap[ev.next.u] ?? ''}`);
      } else {
        if (ev.prev && ev.prev.u > 0) diffs.push('変化予報なし');
      }
    }
    if (!ev.prev || ev.prev.c !== ev.next.c) {
      const labels = ['とても空き','やや空き','ふつう','やや混雑','とても混雑'];
      diffs.push(`混雑: ${ev.prev ? labels[ev.prev.c] + '→' : ''}${labels[ev.next.c]}`);
    }

    const body = diffs.join(' / ');
    pushToast(name, body || '更新がありました');
  }
);
</script>

<style scoped>
/* スタイルは変更ありません */
.nav-view {
  position: relative;
  width: 100%;
  height: 100vh;
}

.loading-overlay {
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
  width: 100%;
  height: 100%;
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

/* ★ 接続状態パネル */
.conn-panel {
  background: #ffffff;
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  margin-bottom: 10px;
  min-width: 250px;
}
.conn-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.conn-row:last-child { margin-bottom: 0; }
.chip {
  display: inline-block;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #f1f3f5;
  color: #333;
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
  margin-left: auto; /* ボタンを右寄せ */
}
.join-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spot-list-toggle {
  padding: 10px 15px;
  font-size: 1rem;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  box-shadow: 0 2px 5px rgba(0,0,0,0.2);
  margin-bottom: 10px;
  flex-shrink: 0;
}

.spot-list {
  background: white;
  border-radius: 5px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  padding: 10px;
  max-height: 75vh;
  overflow-y: auto;
  min-width: 250px;
}

.spot-list h3 {
  margin-top: 0;
  margin-bottom: 10px;
  font-size: 1.1rem;
  border-bottom: 1px solid #eee;
  padding-bottom: 5px;
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
  gap: 8px;
}

.spot-list li:last-child button {
  border-bottom: none;
}

.spot-list li button:hover {
  background-color: #f5f5f5;
}

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
  flex-shrink: 0;
}

.nearby-section {
  margin-top: 15px;
}

.nearby-title {
  color: #555;
  font-size: 1.0rem;
}

.nearby-button {
  padding-left: 16px !important; 
}

/* リアルタイムバッジ */
.rt-badges {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.rt-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 12px;
  font-size: 12px;
  line-height: 1;
  background: #f1f3f5;
  color: #333;
}
.rt-badge.weather { background: #ffe9a8; }
.rt-badge.upcoming { background: #dff0ff; }
.rt-badge.crowd { background: #eee; }

/* トースト */
.toast-stack {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 1100;
}
.toast {
  background: rgba(30, 30, 30, 0.95);
  color: #fff;
  padding: 10px 12px;
  border-radius: 8px;
  min-width: 240px;
  max-width: 360px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.25);
}
.toast strong {
  display: block;
  margin-bottom: 4px;
  font-size: 0.95rem;
}
.toast-body {
  font-size: 0.9rem;
}

.error-view {
  padding: 20px;
  text-align: center;
}
</style>