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
    </div>
    
    <div v-else class="error-view">
      <p>ナビゲーションプランが見つかりません。</p>
      <router-link to="/plan">プラン作成画面に戻る</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useNavStore } from '@/stores/nav';
import { useRouter } from 'vue-router';
import NavMap from '@/components/NavMap.vue';

const navStore = useNavStore();
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


onMounted(() => {
  // navストアにプランがなければプラン作成ページにリダイレクト
  if (!navStore.plan) {
    router.push('/plan');
  }
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
/* ★ 追加ここまで ★ */


.error-view {
  padding: 20px;
  text-align: center;
}
</style>