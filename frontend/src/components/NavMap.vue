<template>
  <div class="nav-map">
    <div ref="mapEl" class="map"></div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch, ref, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const props = defineProps({
  plan: { type: Object, default: null }, // PlanResponse: { route: FeatureCollection, ... }
  pois: { type: Array, default: () => [] } // along_pois (spotのみを想定)
})

// 親から使う公開メソッド
defineExpose({ focusOnSpot })

const mapEl = ref(null)
let map = null
let routeLayer = null
let spotLayerGroup = null
const spotMarkerMap = new Map() // spot_id -> Leaflet Marker

let meMarker = null
let proximityCircle = null
let geoWatchId = null

onMounted(async () => {
  await nextTick()
  initMap()

  if (props.plan?.route) addOrUpdateRoute(props.plan.route)
  addOrUpdateSpots(props.pois || [])
  fitToData()
  startLocalGeolocation()
})

onBeforeUnmount(() => {
  if (geoWatchId) {
    navigator.geolocation.clearWatch(geoWatchId)
    geoWatchId = null
  }
  map?.remove?.()
  map = null
})

watch(() => props.plan?.route, (fc) => {
  if (!map) return
  addOrUpdateRoute(fc)
  fitToData()
})

watch(() => props.pois, (list) => {
  if (!map) return
  addOrUpdateSpots(list || [])
  fitToData()
})

function initMap() {
  map = L.map(mapEl.value, { zoomControl: false }).setView([35.681, 139.767], 10)
  L.control.zoom({ position: 'topleft' }).addTo(map)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map)
}

// --------- ルート描画（car=青実線、foot=オレンジ破線） ---------
function addOrUpdateRoute(featureCollection) {
  if (routeLayer) {
    routeLayer.clearLayers()
    map.removeLayer(routeLayer)
    routeLayer = null
  }
  if (!featureCollection?.features?.length) return

  routeLayer = L.geoJSON(featureCollection, {
    style: (f) => {
      const mode = f?.properties?.mode || 'car'
      return mode === 'foot'
        ? { color: '#f97316', weight: 4, dashArray: '6 6' }
        : { color: '#1d4ed8', weight: 5 }
    }
  }).addTo(map)
}

// --------- スポット描画（番号付きピン＋ポップアップ） ---------
function addOrUpdateSpots(list) {
  if (spotLayerGroup) {
    spotLayerGroup.clearLayers()
    map.removeLayer(spotLayerGroup)
  }
  spotLayerGroup = L.layerGroup().addTo(map)
  spotMarkerMap.clear()

  ;(list || []).forEach((p, idx) => {
    if (p.lat == null || p.lon == null) return
    const icon = L.divIcon({
      className: 'poi-pin',
      html: `<span>${idx + 1}</span>`,
      iconSize: [28, 28],
      iconAnchor: [14, 28],
      popupAnchor: [0, -28]
    })
    const m = L.marker([p.lat, p.lon], { icon })
      .bindPopup(`<strong>${idx + 1}. ${escapeHtml(p.name || '無名スポット')}</strong>`, { closeButton: true })
      .addTo(spotLayerGroup)

    spotMarkerMap.set(p.spot_id || `@${idx}`, m)
  })
}

// NavView から呼ばれる
function focusOnSpot(spotId, opts = {}) {
  const m = spotMarkerMap.get(spotId)
  if (!m) return
  map.flyTo(m.getLatLng(), 16, { duration: 0.6 })
  if (opts.fallbackTitle) m.setPopupContent(`<strong>${escapeHtml(opts.fallbackTitle)}</strong>`)
  m.openPopup()
}

// --------- ビューポート調整 ---------
function fitToData() {
  const boundsList = []

  if (routeLayer) boundsList.push(routeLayer.getBounds())
  if (spotLayerGroup && spotLayerGroup.getLayers().length) {
    boundsList.push(L.featureGroup(spotLayerGroup.getLayers()).getBounds())
  }
  if (!boundsList.length) return

  let b = boundsList[0]
  for (let i = 1; i < boundsList.length; i++) b = b.extend(boundsList[i])
  map.fitBounds(b, { padding: [40, 40], maxZoom: 14 })
}

// --------- 現在地（見た目用）＋近接半径の可視化 ---------
function startLocalGeolocation() {
  if (!('geolocation' in navigator)) return
  geoWatchId = navigator.geolocation.watchPosition(
    (pos) => {
      const latlng = [pos.coords.latitude, pos.coords.longitude]
      if (!meMarker) {
        meMarker = L.circleMarker(latlng, {
          radius: 6, color: '#2563eb', weight: 2, fill: true, fillOpacity: 1
        }).addTo(map)
      } else {
        meMarker.setLatLng(latlng)
      }
      drawProximity(latlng)
    },
    (err) => console.warn('[geo]', err),
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
  )
}

function drawProximity(latlng) {
  const mode = nearestMode([latlng[1], latlng[0]], props.plan?.route) // [lon,lat] で計算
  const r = mode === 'car' ? 300 : 10
  if (!proximityCircle) {
    proximityCircle = L.circle(latlng, {
      radius: r, color: '#16a34a', weight: 2, dashArray: '4 4',
      fillColor: '#22c55e', fillOpacity: 0.15
    }).addTo(map)
  } else {
    proximityCircle.setLatLng(latlng).setRadius(r)
  }
}

// --------- ユーティリティ ---------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))
}

/** route の最寄り線分の mode を雑に推定（小距離の平面近似） */
function nearestMode([lon, lat], fc) {
  if (!fc?.features?.length) return 'car'
  let best = { d2: Infinity, mode: 'car' }
  for (const f of fc.features) {
    const mode = f.properties?.mode || 'car'
    const coords = f.geometry?.type === 'LineString'
      ? f.geometry.coordinates
      : f.geometry?.type === 'MultiLineString'
        ? f.geometry.coordinates.flat()
        : []
    for (let i = 1; i < coords.length; i++) {
      const d2 = pointSegDist2([lon, lat], coords[i - 1], coords[i])
      if (d2 < best.d2) best = { d2, mode }
    }
  }
  return best.mode
}

function pointSegDist2(p, a, b) {
  const toRad = (x) => x * Math.PI / 180
  const R = 6371000
  const [λp, φp] = [toRad(p[0]), toRad(p[1])]
  const [λa, φa] = [toRad(a[0]), toRad(a[1])]
  const [λb, φb] = [toRad(b[0]), toRad(b[1])]
  const x = (λ) => R * λ
  const y = (φ) => R * φ
  const xp = x(λp), yp = y(φp)
  const xa = x(λa), ya = y(φa)
  const xb = x(λb), yb = y(φb)
  const vx = xb - xa, vy = yb - ya
  const wx = xp - xa, wy = yp - ya
  const c1 = vx * wx + vy * wy
  if (c1 <= 0) return (xp - xa) ** 2 + (yp - ya) ** 2
  const c2 = vx * vx + vy * vy
  if (c2 <= c1) return (xp - xb) ** 2 + (yp - yb) ** 2
  const t = c1 / c2
  const xh = xa + t * vx, yh = ya + t * vy
  return (xp - xh) ** 2 + (yp - yh) ** 2
}
</script>

<style scoped>
.nav-map, .map {
  width: 100%;
  height: 100%;
  min-height: 420px;
}

/* 番号付きピン */
.poi-pin {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #fff;
  border: 2px solid #111827;
  box-shadow: 0 2px 8px rgba(0,0,0,.2);
  display: grid;
  place-items: center;
  transform: translateY(-2px);
  font-weight: 800;
  font-size: 13px;
}
.poi-pin span { line-height: 1; }
</style>
