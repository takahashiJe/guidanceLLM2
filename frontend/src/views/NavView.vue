<template>
  <div class="nav-view">
    <div v-if="navStore.isLoading" class="loading-overlay">
      <p>案内プランを生成中です...</p>
    </div>
    <div v-else-if="plan" class="nav-container">
      <div class="map-wrapper">
        <NavMap ref="navMap" :plan="plan" />
      </div>
      <div class="controls">
        <button @click="toggleSpotList" class="spot-list-toggle">
          {{ isSpotListVisible ? 'リストを隠す' : '周遊スポット一覧' }}
        </button>
        <div v-if="isSpotListVisible" class="spot-list">
          <h3>周遊スポット</h3>
          <ul>
            <li v-for="poi in sortedPois" :key="poi.spot_id">
              <button @click="focusOnSpot(poi)">
                <span class="order-index">{{ poi.order_index }}</span>
                {{ poi.name }}
              </button>
            </li>
          </ul>
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

// order_index を基準にPOIをソートする
const sortedPois = computed(() => {
  if (plan.value && plan.value.along_pois) {
    // Array.prototype.slice() を使ってシャローコピーを作成してからソートする
    return [...plan.value.along_pois].sort((a, b) => a.order_index - b.order_index);
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
}

.spot-list {
  background: white;
  border-radius: 5px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  padding: 10px;
  max-height: 50vh;
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


.error-view {
  padding: 20px;
  text-align: center;
}
</style>