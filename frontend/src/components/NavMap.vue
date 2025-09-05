<template>
  <div ref="mapEl" class="map"></div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch, ref, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const props = defineProps({
  plan: { type: Object, default: null },
  lang: { type: String, default: 'ja' },
})

const mapEl = ref(null)
let map
let baseLayer
let routeGroup
let spotGroup
let hereMarker
let watchId = null

// spot_id -> marker の索引
let spotIndex = new Map()

function ensureMap () {
  if (map) return
  map = L.map(mapEl.value, { zoomControl: true, preferCanvas: true })

  baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map)

  routeGroup = L.layerGroup().addTo(map)
  spotGroup  = L.layerGroup().addTo(map)
}

function segStyle (f) {
  const mode = String(f?.properties?.mode || f?.properties?.transport || 'car').toLowerCase()
  const isFoot = mode.includes('foot') || mode.includes('walk') || mode.includes('hike')
  return {
    color: isFoot ? '#ff7f0e' : '#1e90ff',  // 徒歩=オレンジ(破線) / 車=青(実線)
    weight: isFoot ? 5 : 6,
    opacity: 0.9,
    dashArray: isFoot ? '8,8' : null,
    lineJoin: 'round',
    lineCap: 'round',
  }
}

function pickName(s, lang='ja') {
  return (
    s?.official_name?.[lang] ||
    s?.[`name_${lang}`] ||
    s?.name ||
    s?.spot_id ||
    ''
  )
}

function drawSpots (plan) {
  spotGroup.clearLayers()
  spotIndex = new Map()

  const ordered = (plan?.legs || [])
    .map(l => l?.spot)
    .filter(s => s && Number.isFinite(+s.lat) && Number.isFinite(+s.lon))

  let idx = 1
  for (const s of ordered) {
    const sid = String(s.spot_id || s.id)
    const icon = L.divIcon({
      className: 'spot-idx',
      html: `<div class="badge">${idx}</div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    })
    const m = L.marker([+s.lat, +s.lon], { icon })
      .bindPopup(`${pickName(s, props.lang)}<br><small>#${sid}</small>`)
      .addTo(spotGroup)
    spotIndex.set(sid, m)
    idx++
  }

  // access_points
  for (const ap of (plan?.access_points || [])) {
    if (ap?.lat != null && ap?.lon != null) {
      L.circleMarker([+ap.lat, +ap.lon], { radius: 4, color: '#444', weight: 2, fillOpacity: 0.8 })
        .bindPopup(ap?.name || 'access')
        .addTo(spotGroup)
    }
  }
}

function drawPlan (plan) {
  ensureMap()
  routeGroup.clearLayers()
  spotGroup.clearLayers()
  spotIndex = new Map()

  if (!plan?.route) return

  const route = L.geoJSON(plan.route, { style: segStyle }).addTo(routeGroup)

  try {
    const b = route.getBounds()
    if (b.isValid()) map.fitBounds(b.pad(0.08))
  } catch {}

  drawSpots(plan)
}

function startHere () {
  if (!navigator.geolocation) return
  watchId = navigator.geolocation.watchPosition(
    (pos) => {
      const latlng = [pos.coords.latitude, pos.coords.longitude]
      if (!hereMarker) {
        hereMarker = L.circleMarker(latlng, {
          radius: 6, color: '#0066ff', fillColor: '#2f7bff', fillOpacity: 1, weight: 2,
        }).addTo(map)
      } else {
        hereMarker.setLatLng(latlng)
      }
    },
    () => {},
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
  )
}

onMounted(async () => {
  ensureMap()
  await nextTick()
  drawPlan(props.plan)
  startHere()
})

watch(() => props.plan, (p) => drawPlan(p), { deep: true })
watch(() => props.lang, () => drawSpots(props.plan))

onBeforeUnmount(() => {
  if (watchId) navigator.geolocation.clearWatch(watchId)
})

// 親から呼ぶ公開API
defineExpose({
  focusSpotById(spotId) {
    const m = spotIndex.get(String(spotId))
    if (map && m) {
      const ll = m.getLatLng()
      map.setView(ll, Math.max(map.getZoom(), 16), { animate: true })
      m.openPopup?.()
    }
  },
})
</script>

<style scoped>
.map {
  width: 100%;
  height: 70vh;
  background: #eef2f5;
  border-radius: 12px;
}
.spot-idx .badge{
  position: relative;
  display: grid;
  place-items: center;
  width: 26px; height: 26px;
  border-radius: 999px;
  background: #0b5fff; color: #fff; font-weight: 700; font-size: 12px;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #0b5fff55;
}
</style>
