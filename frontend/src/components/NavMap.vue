<template>
  <div class="map-wrap">
    <div ref="mapEl" class="map-el"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png'
import shadowUrl from 'leaflet/dist/images/marker-shadow.png'
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl })

const props = defineProps({ plan: { type: Object, default: () => ({}) } })

const mapEl = ref(null)
let map, routeLayer, youMarker
let geoWatchId = null

function renderRoute() {
  if (!map || !props.plan?.route) return
  if (routeLayer) routeLayer.remove()
  routeLayer = L.geoJSON(props.plan.route, { style: () => ({ weight: 5 }) }).addTo(map)
  try { map.fitBounds(routeLayer.getBounds(), { padding: [20, 20] }) } catch {}
}

onMounted(() => {
  map = L.map(mapEl.value, { zoomControl: true })
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; OpenStreetMap',
  }).addTo(map)

  renderRoute()
  ;(props.plan.along_pois || []).forEach(p => {
    L.marker([p.lat, p.lon]).addTo(map).bindPopup(p.name || p.spot_id)
  })
  youMarker = L.circleMarker([0, 0], { radius: 6 }).addTo(map)
  geoWatchId = navigator.geolocation.watchPosition(
    (pos) => youMarker.setLatLng([pos.coords.latitude, pos.coords.longitude]),
    () => {},
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
  )
})

onBeforeUnmount(() => {
  if (geoWatchId) navigator.geolocation.clearWatch(geoWatchId)
  if (map) map.remove()
  map = routeLayer = youMarker = null
})

watch(() => props.plan, () => renderRoute())
</script>

<style scoped>
.map-wrap { width: 100%; height: 100%; }
.map-el { width: 100%; height: 100%; }
</style>
