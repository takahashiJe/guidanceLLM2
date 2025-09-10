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
                <!-- ★ ここから追加：リアルタイムの最新情報バッジ -->
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
                <!-- ★ 追加ここまで -->
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

      <!-- ★ ここから追加：トースト通知（内容が変わった時だけ） -->
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
      <!-- ★ 追加ここまで -->

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

/* ★ 追加：リアルタイム用ストア */
import { useRtStore } from '@/stores/rt';

const navStore = useNavStore();
const rtStore = useRtStore();
const router = useRouter();
const plan = computed(() => navStore.plan);
const navMap = ref(null);
const isSpotListVisible = ref(true);

// ★修正 1: 周遊スポット (Waypoints) リスト。 nearest_idx (ルート上のインデックス) でソート
const sortedWaypoints = computed(() => {
  if (plan.value && plan.value.waypoints_info) {
    // バックエンド(nav/tasks.py)が付与した nearest_idx (ルート座標列上の最近接点インデックス) でソート
    return [...plan.value.waypoints_info].sort((a, b) => (a.nearest_idx || 0) - (b.nearest_idx || 0));
  }
  return [];
});

// ★修正 2: 周辺のスポット (AlongPOIs) リスト。 order_index (または nearest_idx) でソート
const sortedAlongPois = computed(() => {
  if (plan.value && plan.value.along_pois) {
    // 元の実装(sortedPois)のロジックを引き継ぎ、order_index (または nearest_idx) でソート
    return [...plan.value.along_pois].sort((a, b) => (a.order_index ?? a.nearest_idx ?? 0) - (b.order_index ?? b.nearest_idx ?? 0));
  }
  return [];
});

/* ★ 追加：spot_id → name のマップ（通知用に名前表示） */
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

/* ★ 追加：トースト通知（最新の変更だけ順次表示） */
const toasts = ref([]);
/** make toast */
function pushToast(title, body, timeoutMs = 4000) {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  toasts.value.push({ id, title, body });
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id);
  }, timeoutMs);
}

// navストアにプランがなければプラン作成ページにリダイレクト
onMounted(() => {
  if (!navStore.plan) {
    router.push('/plan');
    return;
  }
  // ★ 追加：ポーリング開始（A→B→A→B…）
  // waypoints_info をそのまま渡せば、rtストア内で spot_id 抽出・順序設定される
  rtStore.startPolling(plan.value?.waypoints_info || []);
});

onUnmounted(() => {
  // ★ 追加：ポーリング停止
  rtStore.stopPolling();
});

function toggleSpotList() {
  isSpotListVisible.value = !isSpotListVisible.value;
}

function focusOnSpot(poi) {
  if (navMap.value) {
    // NavMapコンポーネントで公開されたメソッドを呼び出す
    navMap.value.flyToSpot(poi.lat, poi.lon);
  }
}

/* ★ 追加：UI表示用の小ユーティリティ */
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
  // 0..4 を 5個のドットで表現（●=混雑, ○=空き）
  const n = Number.isFinite(c) ? Math.max(0, Math.min(4, c)) : 0
  return '○'.repeat(4 - n) + '●'.repeat(n + 1 - 1) // ざっくり視覚化
}
function crowdTitle(doc) {
  if (!doc) return '';
  const labels = ['とても空いている', 'やや空き', 'ふつう', 'やや混雑', 'とても混雑'];
  const c = Math.max(0, Math.min(4, Number(doc.c ?? 0)));
  return `混雑: ${labels[c]}`;
}
/* リストの中で参照しやすいようにラッパ */
function latestBySpot(spotId) {
  return rtStore.getLatest?.(spotId) ?? null;
}

/* ★ 追加：変更時のみ通知（rt.notifyLog を監視） */
watch(
  () => rtStore.notifyLog.length,
  (len, prev) => {
    if (len <= prev) return;
    const ev = rtStore.notifyLog[len - 1];
    const name = spotNameMap.value.get(ev.spot_id) || ev.spot_id;

    // 何が変わったか簡易に要約
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
        // 変化予報が解除されたケース
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
  /* (★修正) 2つのリストが入るため、コントロール全体の高さを制限しスクロール可能に */
  max-height: calc(100vh - 20px); 
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
  flex-shrink: 0; /* (★追加) トグルボタンが縮まないように */
}

.spot-list {
  background: white;
  border-radius: 5px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  padding: 10px;
  max-height: 75vh; /* (★修正) リストコンテナの最大高さを確保 */
  overflow-y: auto;   /* リストコンテナ自体をスクロールさせる */
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

/* ★ ここから追加 ★ */
.nearby-section {
  margin-top: 15px; /* 周遊スポットリストとの間隔 */
}

.nearby-title {
  color: #555; /* タイトル色を少し変える */
  font-size: 1.0rem; /* 少し小さく */
}

.nearby-button {
    /* order-index がないため、テキストのインデントを調整 */
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
/* ★ 追加ここまで ★ */

.error-view {
  padding: 20px;
  text-align: center;
}
</style>
