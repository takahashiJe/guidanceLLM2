<!-- src/components/NavMap.vue -->
<template>
  <div ref="mapEl" class="map"></div>
</template>

<script setup>
import { onMounted, watch, ref } from 'vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const props = defineProps({
  plan:  { type: Object, default: null },     // ナビ計画レスポンス
  stops: { type: Array,  default: () => [] }, // [{spot_id, name, lat, lon}]  ※順序付き
  lang:  { type: String, default: 'ja' },
});

const mapEl = ref(null);
let map;
let layers = {
  car: null,
  foot: null,
  spots: null,
  access: null,
  here: null
};
const spotMarkerMap = new Map(); // spot_id -> marker

// ----------------------------------------------------
// 基本セットアップ
// ----------------------------------------------------
function ensureMap() {
  if (map) return;
  map = L.map(mapEl.value, { zoomControl: true });

  // タイル：オンライン（Service Worker があればそちらが掴む）
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map);

  layers.car   = L.layerGroup().addTo(map);
  layers.foot  = L.layerGroup().addTo(map);
  layers.spots = L.layerGroup().addTo(map);
  layers.access= L.layerGroup().addTo(map);
}

// ----------------------------------------------------
// ルート描画：car = 青実線、foot = オレンジ破線
// ----------------------------------------------------
function drawRoute(plan) {
  layers.car.clearLayers();
  layers.foot.clearLayers();

  if (!plan?.polyline?.length) return;

  const coords = plan.polyline.map(([lon, lat]) => [lat, lon]);

  // セグメント情報がある場合はそれで分割して描く
  if (Array.isArray(plan.segments) && plan.segments.length) {
    for (const seg of plan.segments) {
      const pts = coords.slice(seg.start_idx, seg.end_idx + 1);
      if (pts.length < 2) continue;

      if (seg.mode === 'car') {
        L.polyline(pts, { color: '#2563eb', weight: 5, opacity: 0.95 }).addTo(layers.car);
      } else {
        // foot
        L.polyline(pts, {
          color: '#f59e0b', weight: 5, opacity: 0.95, dashArray: '8 8', lineCap: 'round'
        }).addTo(layers.foot);
      }
    }
  } else {
    // セグメントが無い場合は全体を車線として描画
    L.polyline(coords, { color: '#2563eb', weight: 5 }).addTo(layers.car);
  }

  // 画面合わせ
  try {
    const all = L.featureGroup([layers.car, layers.foot]);
    const b = all.getBounds();
    if (b.isValid()) map.fitBounds(b, { padding: [24, 24] });
  } catch {}
}

// ----------------------------------------------------
// スポット＆アクセス点
// ----------------------------------------------------
function drawSpots(stops, plan) {
  layers.spots.clearLayers();
  layers.access.clearLayers();
  spotMarkerMap.clear();

  // 順序付きスポット（大きめの番号バッジ）
  stops.forEach((s, idx) => {
    if (s.lat == null || s.lon == null) return;

    const marker = L.marker([s.lat, s.lon], {
      icon: L.divIcon({
        className: 'spot-badge',
        html: `<div class="badge"><span>${idx + 1}</span></div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 30],
      })
    }).addTo(layers.spots);

    marker.bindPopup(`<div style="font-weight:600">${s.name}</div><div style="color:#6b7280">#${s.spot_id}</div>`);
    spotMarkerMap.set(s.spot_id, marker);
  });

  // access_points があれば小さめピン（灰色）
  const aps =
    (Array.isArray(plan?.access_points) && plan.access_points) ||
    (Array.isArray(plan?.pois) && plan.pois.filter(p => (p.type || p.category) === 'access_point')) ||
    [];
  aps.forEach((p) => {
    const lat = p.lat ?? p.latitude ?? p.point?.lat ?? p.coordinates?.[1];
    const lon = p.lon ?? p.longitude ?? p.point?.lon ?? p.coordinates?.[0];
    if (lat == null || lon == null) return;

    L.circleMarker([+lat, +lon], {
      radius: 5, color: '#6b7280', fillColor: '#9ca3af', fillOpacity: 0.9, weight: 1.5
    }).addTo(layers.access);
  });
}

// ----------------------------------------------------
// 現在地 & 近接再生
// ----------------------------------------------------
const played = new Set();

function hav(d1, d2) {
  const toRad = (d) => d * Math.PI / 180;
  const R = 6371000;
  const dLat = toRad(d2[0] - d1[0]);
  const dLon = toRad(d2[1] - d1[1]);
  const lat1 = toRad(d1[0]);
  const lat2 = toRad(d2[0]);
  const a = Math.sin(dLat/2)**2 + Math.sin(dLon/2)**2 * Math.cos(lat1) * Math.cos(lat2);
  return 2 * R * Math.asin(Math.sqrt(a));
}

function nearestMode(lat, lon, plan) {
  if (!plan?.polyline?.length) return 'car';
  let best = Infinity, bestIdx = 0;
  for (let i = 0; i < plan.polyline.length; i++) {
    const [x, y] = plan.polyline[i]; // [lon, lat]
    const d = hav([lat, lon], [y, x]);
    if (d < best) { best = d; bestIdx = i; }
  }
  let mode = 'car';
  for (const seg of plan.segments || []) {
    if (bestIdx >= seg.start_idx && bestIdx <= seg.end_idx) {
      mode = seg.mode || 'car';
      break;
    }
  }
  return mode;
}

function audioUrlFor(spotId) {
  const a = (props.plan?.assets || []).find(x => x?.audio?.url && x.spot_id === spotId);
  return a?.audio?.url || null;
}

function tryPlay(spotId) {
  if (played.has(spotId)) return;
  const url = audioUrlFor(spotId);
  if (!url) return;
  // Service Worker / CacheStorage 済み URL をそのまま再生（同一オリジン）
  const audio = new Audio(url);
  audio.play().catch(() => {});
  played.add(spotId);
}

function trackHere(plan, stops) {
  if (!navigator.geolocation) return;
  navigator.geolocation.watchPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;

      // マーカー更新
      if (!layers.here) {
        layers.here = L.circleMarker([latitude, longitude], {
          radius: 6, color: '#2563eb', fillColor: '#93c5fd', fillOpacity: 0.9, weight: 2
        }).addTo(map);
      } else {
        layers.here.setLatLng([latitude, longitude]);
      }

      // 近接半径：最寄りルートのモードに合わせる（車=300m/徒歩=10m）
      const mode = nearestMode(latitude, longitude, plan);
      const radius = mode === 'car' ? 300 : 10;

      // まだ再生していないスポットに対して、現在地との直線距離が radius 未満なら再生
      for (const s of stops) {
        if (s.lat == null || s.lon == null) continue;
        const d = hav([latitude, longitude], [s.lat, s.lon]);
        if (d <= radius) tryPlay(s.spot_id);
      }
    },
    () => {},
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
  );
}

// ----------------------------------------------------
// 外からスポットにフォーカスする API
// ----------------------------------------------------
function focusSpot(id) {
  const m = spotMarkerMap.get(id);
  if (!m) return;
  const ll = m.getLatLng();
  map.setView(ll, Math.max(map.getZoom(), 16), { animate: true });
  m.openPopup();
}
defineExpose({ focusSpot });

// ----------------------------------------------------
// ライフサイクル
// ----------------------------------------------------
onMounted(() => {
  ensureMap();
  drawRoute(props.plan);
  drawSpots(props.stops, props.plan);
  trackHere(props.plan, props.stops);
});

watch(() => props.plan, (p) => {
  if (!map) return;
  drawRoute(p);
}, { deep: true });

watch(() => props.stops, (s) => {
  if (!map) return;
  drawSpots(s, props.plan);
}, { deep: true });
</script>

<style scoped>
.map { width: 100%; height: calc(100vh - 110px); background:#f8fafc; }

/* 番号付きスポットバッジ */
.spot-badge .badge {
  background:#1d4ed8; color:#fff; width:30px; height:30px;
  border-radius:999px; display:grid; place-items:center;
  border:2px solid #bfdbfe; box-shadow: 0 2px 6px rgba(0,0,0,.2);
}
.spot-badge .badge span { font-weight:700; }
</style>
