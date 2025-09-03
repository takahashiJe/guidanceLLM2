<!-- src/components/NavMap.vue -->
<template>
  <div ref="mapRef" class="map"></div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const props = defineProps({
  plan: { type: Object, required: false, default: null },
})

const mapRef = ref(null)
let map, geoLayer, poiLayer

function renderPlan(plan) {
  if (!map || !plan) return
  // 既存のレイヤをクリア
  if (geoLayer) { geoLayer.remove(); geoLayer = null }
  if (poiLayer) { poiLayer.remove(); poiLayer = null }

  // 経路（GeoJSON）
  if (plan.route) {
    geoLayer = L.geoJSON(plan.route, {
      style: { weight: 5 }
    }).addTo(map)
    try {
      map.fitBounds(geoLayer.getBounds(), { padding: [20, 20] })
    } catch (_) {}
  }

  // 沿道POI
  if (Array.isArray(plan.along_pois)) {
    poiLayer = L.layerGroup(
      plan.along_pois.map(p =>
        L.marker([p.lat, p.lon]).bindPopup(`<b>${p.name || p.spot_id}</b>`)
      )
    ).addTo(map)
  }
}

onMounted(() => {
  if (!mapRef.value) return
  map = L.map(mapRef.value, { zoomControl: true }).setView([39.22, 139.90], 12)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map)

  renderPlan(props.plan)
})

onBeforeUnmount(() => {
  if (map) map.remove()
})

watch(() => props.plan, (p) => {
  renderPlan(p)
})
</script>

<style scoped>
.map { width: 100%; height: calc(100vh - 140px); }
</style>
