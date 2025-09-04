<!-- src/components/NavMap.vue -->
<template>
  <div class="map" ref="mapEl"></div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch, ref } from 'vue'
import { useNavStore } from '@/stores/nav'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

/**
 * 受け取り: backendから返ってくる Plan 全体
 *  - plan.polyline: [[lon,lat], ...]
 *  - plan.segments: [{ mode: "car"|"foot", start_idx:number, end_idx:number }, ...]
 *  - plan.assets:   [{ spot_id, audio:{url} }, ...]
 *  - plan.access_points or plan.along_pois: Array<{spot_id?, location{lat,lon} | lat,lon}>
 */
const props = defineProps({
  plan: { type: Object, default: null }
})

/* -------------------------------
   地図・レイヤ
-------------------------------- */
const mapEl = ref(null)
let map
let routeGroup         // ルート（車/徒歩の描き分け）
let waypointsGroup     // 周遊スポット（順番付き）
let accessPointsGroup  // access_points
let hereMarker         // 現在地
let proxCircle         // 近接半径表示

/* -------------------------------
   ストア・POI辞書・アセットURL
-------------------------------- */
const nav = useNavStore()           // lang, waypoints など
let pois = null                     // /pois.json の配列
let poiIndex = Object.create(null)  // spot_id -> poi
let assetBySpot = new Map()         // spot_id -> audio url
const played = new Set()            // 再生済みの spot_id

/* -------------------------------
   マップ初期化
-------------------------------- */
function ensureMap () {
  if (map) return
  map = L.map(mapEl.value, { zoomControl: true })
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
  }).addTo(map)

  routeGroup        = L.layerGroup().addTo(map)
  waypointsGroup    = L.layerGroup().addTo(map)
  accessPointsGroup = L.layerGroup().addTo(map)
}

/* -------------------------------
   /pois.json を一度だけロード
-------------------------------- */
async function loadPoisOnce () {
  if (pois) return
  try {
    const r = await fetch('/pois.json', { credentials: 'same-origin' })
    pois = await r.json()
    poiIndex = Object.create(null)
    for (const p of pois) {
      poiIndex[p.spot_id] = p
    }
  } catch (e) {
    // 失敗しても動作は続ける（名称は spot_id フォールバック）
    console.warn('[NavMap] failed to load /pois.json', e)
  }
}

/* -------------------------------
   表示名（言語に応じて）
-------------------------------- */
function spotTitle (spotId) {
  const p = poiIndex[spotId]
  if (!p) return spotId
  const names = p.official_name || {}
  return names[nav.lang] || names.ja || p.name || spotId
}

/* -------------------------------
   ルート描画（車=青実線 / 徒歩=オレンジ破線）
-------------------------------- */
const STYLE_CAR  = { color: '#1976d2', weight: 5 }
const STYLE_FOOT = { color: '#ff9800', weight: 5, dashArray: '6,8' }

function drawRoute (plan) {
  routeGroup.clearLayers()
  if (!plan?.polyline?.length) return

  const coords = plan.polyline.map(([lon, lat]) => [lat, lon])

  if (Array.isArray(plan.segments) && plan.segments.length) {
    for (const seg of plan.segments) {
      const a = Math.max(0, seg.start_idx | 0)
      const b = Math.min(coords.length - 1, (seg.end_idx | 0))
      const part = coords.slice(a, b + 1)
      if (part.length >= 2) {
        const style = seg.mode === 'foot' ? STYLE_FOOT : STYLE_CAR
        L.polyline(part, style).addTo(routeGroup)
      }
    }
  } else {
    // セグメント情報が無い場合は全部「車」扱い
    L.polyline(coords, STYLE_CAR).addTo(routeGroup)
  }

  // ビューポート調整
  try {
    const b = routeGroup.getBounds()
    if (b.isValid()) map.fitBounds(b, { padding: [20, 20] })
  } catch {}
}

/* -------------------------------
   スポット & アクセスポイントのピン
-------------------------------- */
function numberIconHtml (n) {
  return `<div class="wp">
    <span class="badge">${n}</span>
  </div>`
}

function addWaypointPins () {
  waypointsGroup.clearLayers()
  if (!nav?.waypoints?.length) return

  let idx = 1
  for (const spotId of nav.waypoints) {
    const poi = poiIndex[spotId]
    if (!poi?.coordinates) continue
    const lat = poi.coordinates.latitude
    const lon = poi.coordinates.longitude

    const icon = L.divIcon({
      html: numberIconHtml(idx++),
      className: 'wp-icon',
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    })

    const marker = L.marker([lat, lon], { icon })
      .bindTooltip(spotTitle(spotId), {
        permanent: true,
        direction: 'top',
        className: 'poi-label'
      })

    waypointsGroup.addLayer(marker)
  }
}

function addAccessPoints () {
  accessPointsGroup.clearLayers()
  const list = props.plan?.access_points || props.plan?.along_pois || []
  for (const it of list) {
    const lat = it.location?.lat ?? it.lat
    const lon = it.location?.lon ?? it.lon
    if (typeof lat !== 'number' || typeof lon !== 'number') continue
    const name = it.spot_id ? spotTitle(it.spot_id) : (it.name || 'access')

    const m = L.circleMarker([lat, lon], {
      radius: 5,
      color: '#666',
      weight: 2,
      fillColor: '#fff',
      fillOpacity: 1
    }).bindTooltip(name, {
      permanent: false,
      direction: 'top',
      className: 'poi-label'
    })

    accessPointsGroup.addLayer(m)
  }
}

/* -------------------------------
   現在地ウォッチ & 近接再生
-------------------------------- */
let geoWatchId = null

function haversine (lat1, lon1, lat2, lon2) {
  const R = 6371000 // meters
  const toRad = (d) => d * Math.PI / 180
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLon/2)**2
  return 2 * R * Math.asin(Math.sqrt(a))
}

// 位置に最も近い polyline のインデックスを返す
function nearestPolylineIndex (lat, lon, plan) {
  if (!plan?.polyline?.length) return -1
  let best = -1
  let bestD = Infinity
  for (let i = 0; i < plan.polyline.length; i++) {
    const [x, y] = plan.polyline[i] // [lon,lat]
    const d = haversine(lat, lon, y, x)
    if (d < bestD) { bestD = d; best = i }
  }
  return best
}

// その位置に応じた近接半径（車=300m / 徒歩=10m）
function currentRadiusByMode (lat, lon, plan) {
  const idx = nearestPolylineIndex(lat, lon, plan)
  if (idx < 0 || !Array.isArray(plan?.segments)) return 300
  const seg = plan.segments.find(s => idx >= (s.start_idx|0) && idx <= (s.end_idx|0))
  return (seg && seg.mode === 'foot') ? 10 : 300
}

// 近接チェック & 再生（各スポット一度だけ）
async function checkProximityAndPlay (lat, lon) {
  const radius = currentRadiusByMode(lat, lon, props.plan)

  // 半径可視化
  if (!proxCircle) {
    proxCircle = L.circle([lat, lon], { radius, color: '#2196f3', weight: 1, fillOpacity: 0.06 })
      .addTo(map)
  } else {
    proxCircle.setLatLng([lat, lon]).setRadius(radius)
  }

  // 対象は「周遊スポット」のみ
  for (const spotId of nav.waypoints || []) {
    if (played.has(spotId)) continue
    const poi = poiIndex[spotId]
    if (!poi?.coordinates) continue
    const d = haversine(lat, lon, poi.coordinates.latitude, poi.coordinates.longitude)
    if (d <= radius) {
      const url = assetBySpot.get(spotId)
      if (url) {
        try {
          const resp = await caches.match(url) || await fetch(url, { credentials: 'same-origin' })
          const blob = await resp.blob()
          const blobUrl = URL.createObjectURL(blob)
          const audio = new Audio(blobUrl)
          audio.play().catch(() => {
            // モバイルの自動再生制限で失敗しても、以後の再生機会に任せる
          })
          // 再生キューに入れたら一度だけ扱い
          played.add(spotId)
          // 後片付け
          audio.addEventListener('ended', () => URL.revokeObjectURL(blobUrl))
        } catch (e) {
          console.warn('[NavMap] audio play failed:', e)
        }
      }
    }
  }
}

function startGeolocation () {
  if (!('geolocation' in navigator)) return
  geoWatchId = navigator.geolocation.watchPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords
      const ll = [latitude, longitude]

      if (!hereMarker) {
        hereMarker = L.circleMarker(ll, {
          radius: 6,
          color: '#1976d2',
          weight: 3,
          fillColor: '#fff',
          fillOpacity: 1
        }).addTo(map)
      } else {
        hereMarker.setLatLng(ll)
      }

      // 近接半径 & 再生
      checkProximityAndPlay(latitude, longitude)
    },
    (err) => {
      console.warn('[NavMap] geolocation error', err)
    },
    { enableHighAccuracy: true, maximumAge: 3000, timeout: 10000 }
  )
}

function stopGeolocation () {
  if (geoWatchId != null) {
    navigator.geolocation.clearWatch(geoWatchId)
    geoWatchId = null
  }
}

/* -------------------------------
   プラン受領時のセットアップ
-------------------------------- */
function prepareAssetsIndex (plan) {
  assetBySpot = new Map()
  for (const a of (plan?.assets || [])) {
    if (a?.spot_id && a?.audio?.url) {
      assetBySpot.set(a.spot_id, a.audio.url)
    }
  }
}

async function renderAll (plan) {
  if (!map) return
  await loadPoisOnce()
  prepareAssetsIndex(plan)
  drawRoute(plan)
  addWaypointPins()
  addAccessPoints()
}

/* -------------------------------
   ライフサイクル
-------------------------------- */
onMounted(async () => {
  ensureMap()
  await renderAll(props.plan)
  startGeolocation()
})

onBeforeUnmount(() => {
  stopGeolocation()
})

watch(() => props.plan, async (p) => {
  played.clear()          // 新しいプランでは再生履歴をリセット
  await renderAll(p)
}, { deep: true })
</script>

<style scoped>
.map { width: 100%; height: 100%; }

/* 番号バッジ */
.wp-icon { background: transparent; }
.wp .badge{
  display:inline-flex; align-items:center; justify-content:center;
  width:28px; height:28px;
  border-radius:50%;
  background:#1976d2; color:#fff; font-weight:700; font-size:12px;
  box-shadow: 0 1px 3px rgba(0,0,0,.3);
}

/* ラベル（常時表示でも見やすく） */
.poi-label {
  background: rgba(255,255,255,.9);
  color:#333;
  border: 1px solid rgba(0,0,0,.15);
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 12px;
}
</style>
