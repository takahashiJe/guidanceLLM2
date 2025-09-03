<template>
  <div ref="mapEl" class="leaflet"></div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const props = defineProps({
  route: { type: Object, default: null },        // GeoJSON FeatureCollection
  along: { type: Array,  default: () => [] },    // POI 配列
  userPos: { type: Object, default: () => ({ lat: 0, lon: 0 }) },
  proximityRadius: { type: Number, default: 250 }
})

const mapEl = ref(null)
let map, routeLayer, userMarker, radiusCircle, poiLayer

function ensureMap () {
  if (map) return
  map = L.map(mapEl.value, { zoomControl: true })
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap'
  }).addTo(map)

  // 初期中心
  map.setView([props.userPos.lat, props.userPos.lon], 12)

  routeLayer = L.geoJSON(null, { style: { weight: 5, opacity: 0.9 } }).addTo(map)
  poiLayer   = L.layerGroup().addTo(map)
  userMarker = L.marker([props.userPos.lat, props.userPos.lon]).addTo(map)
  radiusCircle = L.circle([props.userPos.lat, props.userPos.lon], {
    radius: props.proximityRadius
  }).addTo(map)
}

function drawRoute () {
  routeLayer.clearLayers()
  if (props.route) {
    routeLayer.addData(props.route)
    try {
      map.fitBounds(routeLayer.getBounds(), { padding: [20, 20] })
    } catch {}
  }
}

function drawPOIs () {
  poiLayer.clearLayers()
  if (!props.along?.length) return
  props.along.forEach(p => {
    L.marker([p.lat, p.lon]).addTo(poiLayer).bindPopup(p.name || p.spot_id)
  })
}

function updateUser () {
  if (!map) return
  userMarker.setLatLng([props.userPos.lat, props.userPos.lon])
  radiusCircle.setLatLng([props.userPos.lat, props.userPos.lon])
  radiusCircle.setRadius(props.proximityRadius)
}

onMounted(() => {
  ensureMap()
  drawRoute()
  drawPOIs()
  updateUser()
})

watch(() => props.route, drawRoute, { deep: true })
watch(() => props.along, drawPOIs, { deep: true })
watch(() => [props.userPos, props.proximityRadius], updateUser, { deep: true })
</script>

<style scoped>
.leaflet { width: 100%; height: 100%; }
</style>
