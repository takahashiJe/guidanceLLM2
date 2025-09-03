<template>
  <section class="panel">
    <div class="head">
      <h2>ナビ</h2>
      <RouterLink to="/plan" class="btn small">プランへ</RouterLink>
    </div>

    <div class="row">
      <label>半径 {{ radius }} m</label>
      <input type="range" min="50" max="500" step="10" v-model.number="radius" />
    </div>

    <NavMap
      class="map"
      :route="route"
      :along="along"
      :user-pos="userPos"
      :proximity-radius="radius"
    />
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useNavStore } from '@/stores/nav'
import NavMap from '@/components/NavMap.vue'

const nav = useNavStore()
const { route, along } = storeToRefs(nav)

const radius = ref(250)
const userPos = ref({ lat: 39.2201, lon: 139.9006 })

// シンプルな現在地ウォッチ（必要なら geolocation に置換）
onMounted(() => {
  if ('geolocation' in navigator) {
    navigator.geolocation.watchPosition(
      (pos) => {
        userPos.value = { lat: pos.coords.latitude, lon: pos.coords.longitude }
      },
      (err) => console.warn('[geo] error', err),
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 }
    )
  }
})
</script>

<style scoped>
.panel { display: grid; gap: 12px; }
.head { display: flex; align-items: center; justify-content: space-between; }
.map { height: calc(100dvh - 140px); border-radius: 12px; overflow: hidden; }
.btn.small { padding: 6px 10px; border: 1px solid #ddd; border-radius: 8px; text-decoration: none; color: #222; background: #fafafa; }
</style>
