<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useNavStore } from '@/stores/nav'
import NavMap from '@/components/NavMap.vue'

const router = useRouter()
const nav = useNavStore()

// 注目すべきスポットの座標を計算する
const focusedCoords = computed(() => {
  const focusedSpot = nav.focusedWaypoint
  if (!focusedSpot) return null

  // alongPoisの中から座標情報を見つける
  // 見つからなければnullを返す
  const spotInfo = nav.alongPois.find(p => p.spot_id === focusedSpot.spot_id)
  return spotInfo?.lonlat || null
})

function handleEndTrip() {
  nav.reset()
  router.push('/')
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
      <button @click="nav.focusNextWaypoint()">次のスポットへ注目</button>
      <button @click="handleEndTrip">ナビゲーション終了</button>
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
  top: 20px;
  right: 20px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

button {
  padding: 10px 15px;
  font-size: 16px;
  color: white;
  background-color: #007bff;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  box-shadow: 0 2px 5px rgba(0,0,0,0.2);
  transition: background-color 0.2s;
}
button:hover {
  background-color: #0056b3;
}
</style>