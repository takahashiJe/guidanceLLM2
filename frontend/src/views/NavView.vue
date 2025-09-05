<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useNavStore } from '@/stores/nav';
import NavMap from '@/components/NavMap.vue';

const router = useRouter();
const nav = useNavStore();

// ★ waypointsのIDリストとalong_poisの詳細情報を組み合わせて、UIで使えるスポットリストを生成
const waypointDetails = computed(() => {
  if (!nav.plan || !nav.plan.waypoints) return [];
  // plan.waypoints には {spot_id: ...} の配列が入っている
  return nav.plan.waypoints
    .map(wp => {
      // along_pois から完全な情報を見つける
      return nav.plan.along_pois.find(poi => poi.spot_id === wp.spot_id);
    })
    .filter(Boolean); // 見つからなかったもの（undefined）を除外
});


// 注目すべきスポットの座標を計算する
const focusedCoords = computed(() => {
  const focusedSpotInfo = nav.focusedWaypoint;
  if (!focusedSpotInfo) return null;

  // alongPois リストから座標を検索する
  const spotDetails = nav.alongPois.find(p => p.spot_id === focusedSpotInfo.spot_id);
  return spotDetails?.lonlat || null;
});

function handleEndTrip() {
  nav.reset();
  router.push('/');
}
</script>

<template>
  <div class="nav-view">
    <NavMap
      v-if="nav.plan"
      :route-geojson="nav.plan.route"
      :pois="nav.plan.along_pois"
      :focus-coords="focusedCoords"
    />
    <div v-else class="loading">
      <p>プランを読み込んでいます...</p>
    </div>

    <div v-if="nav.plan" class="nav-controls">
      <h4>スポットリスト</h4>
      <button 
        v-for="spot in waypointDetails" 
        :key="spot.spot_id"
        @click="nav.focusOnWaypointById(spot.spot_id)"
      >
        {{ spot.name.ja || spot.spot_id }}
      </button>
      <hr>
      <button @click="handleEndTrip" class="end-trip-btn">ナビゲーション終了</button>
    </div>
  </div>
</template>

<style scoped>
.nav-view {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  font-size: 1.5rem;
}

.nav-controls {
  position: absolute;
  top: 15px;
  right: 15px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background-color: rgba(255, 255, 255, 0.9);
  padding: 12px;
  border-radius: 8px;
  box-shadow: 0 4px 10px rgba(0,0,0,0.15);
  max-height: calc(100vh - 40px);
  overflow-y: auto;
}

h4 {
  margin: 0 0 8px 0;
  text-align: center;
}

button {
  padding: 8px 12px;
  font-size: 14px;
  color: #333;
  background-color: #f0f0f0;
  border: 1px solid #ccc;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.2s;
  text-align: left;
}
button:hover {
  background-color: #e0e0e0;
}

.end-trip-btn {
  background-color: #dc3545;
  color: white;
  border-color: #dc3545;
  margin-top: 8px;
}
.end-trip-btn:hover {
  background-color: #c82333;
}

hr {
  border: none;
  border-top: 1px solid #ddd;
  margin: 8px 0;
}
</style>