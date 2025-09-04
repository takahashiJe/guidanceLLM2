<!-- src/components/NavMap.vue -->
<template>
  <div ref="mapEl" class="map"></div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch, ref, nextTick } from 'vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const props = defineProps({
  plan: { type: Object, required: true },
  lang: { type: String, default: 'ja' },
});

const mapEl = ref(null);
let map, base, routeGroup, poiLayer, apLayer, here;
let played = new Set();
let poiDict = null;
let nearestIdxToMode = [];
let watchId = null;

// ---------- helpers ----------
async function loadPoisDict() {
  if (poiDict) return poiDict;
  try {
    const res = await fetch('/pois.json', { credentials:'same-origin' });
    poiDict = await res.json();
  } catch { poiDict = {}; }
  return poiDict;
}
function poiName(spotId, fallback) {
  const d = poiDict?.[spotId];
  return d?.official_name?.[props.lang] || d?.official_name?.ja || fallback || spotId;
}
function toLatLngs(poly) {
  return (poly || []).map(([lon, lat]) => [lat, lon]);
}
function hav(a, b) {
  const R = 6371000;
  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(b[0] - a[0]);
  const dLon = toRad(b[1] - a[1]);
  const s1 = Math.sin(dLat/2), s2 = Math.sin(dLon/2);
  const aa = s1*s1 + Math.cos(toRad(a[0]))*Math.cos(toRad(b[0]))*s2*s2;
  return 2*R*Math.asin(Math.min(1, Math.sqrt(aa)));
}
function nearestVertexIdx(lat, lon, latlngs) {
  let min = Infinity, idx = 0;
  for (let i=0;i<latlngs.length;i++) {
    const d = hav([lat,lon], latlngs[i]);
    if (d < min) { min = d; idx = i; }
  }
  return idx;
}

// ---------- map ----------
function ensureMap() {
  if (map) return;
  map = L.map(mapEl.value, { zoomControl: true, attributionControl: true });
  base = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    subdomains: ['a','b','c'], maxZoom: 19, attribution: '&copy; OpenStreetMap',
  }).addTo(map);
  routeGroup = L.layerGroup().addTo(map);
  poiLayer   = L.layerGroup().addTo(map);
  apLayer    = L.layerGroup().addTo(map);
  setTimeout(() => map.invalidateSize(), 0);
}

// 表示強化：徒歩は白い下敷き + オレンジ破線
function addSegment(ll, mode) {
  if (mode === 'foot') {
    const casing = L.polyline(ll, {
      color: '#ffffff', weight: 9, opacity: 1, lineCap: 'round', interactive: false
    });
    const dash = L.polyline(ll, {
      color: '#ff6d00', weight: 6, opacity: 0.98, lineCap: 'round',
      dashArray: '12,10', className: 'seg-foot', interactive: false
    });
    routeGroup.addLayer(casing);
    routeGroup.addLayer(dash);
    dash.bringToFront();
  } else {
    routeGroup.addLayer(L.polyline(ll, {
      color: '#1976d2', weight: 5, opacity: 0.95, lineCap: 'round', interactive: false
    }));
  }
}

/** plan から順序付きスポットIDリストを推定する（waypoints > assets > pois の順でフォールバック） */
function orderedSpotIds(p) {
  if (Array.isArray(p?.waypoints) && p.waypoints.length) {
    return p.waypoints.map(w => w.spot_id).filter(Boolean);
  }
  if (Array.isArray(p?.assets) && p.assets.length) {
    return p.assets.map(a => a.spot_id).filter(Boolean);
  }
  const pois = p.along_pois || p.pois || [];
  return pois.map(po => po.spot_id).filter(Boolean);
}

function drawPlan(p) {
  if (!map || !p) return;
  routeGroup.clearLayers();
  poiLayer.clearLayers();
  apLayer.clearLayers();
  nearestIdxToMode = [];

  // 1) ルート（segments+polyline を優先利用）
  const latlngs = toLatLngs(p.polyline);
  if (Array.isArray(p.segments) && latlngs.length) {
    p.segments.forEach(seg => {
      const a = Math.max(0, seg.start_idx || 0);
      const b = Math.min(latlngs.length - 1, (seg.end_idx ?? a));
      const ll = latlngs.slice(a, b + 1);
      if (ll.length < 2) return;
      const mode = (seg.mode || 'car').toLowerCase();
      addSegment(ll, mode);
      for (let i=a;i<=b;i++) nearestIdxToMode[i] = mode;
    });
  } else if (p.route?.type === 'FeatureCollection') {
    const feats = p.route.features || [];
    feats.forEach(f => {
      const mode = (f.properties?.mode || 'car').toLowerCase();
      if (f.geometry?.type === 'LineString') {
        const ll = (f.geometry.coordinates || []).map(([lon,lat]) => [lat,lon]);
        if (ll.length >= 2) addSegment(ll, mode);
      }
    });
  }

  // 2) 周遊スポット（順番付き）とその他POI・アクセス点
  const pois = p.along_pois || p.pois || [];
  const order = orderedSpotIds(p);                    // ['spot_001', ...]
  const orderMap = new Map(order.map((id, i) => [id, i])); // spot_id -> index

  // 2-1) まず「順序付きスポット」を大きく描画
  const n = order.length;
  order.forEach((id, idx) => {
    const po = pois.find(x => x.spot_id === id) || {};
    const ll = [po.lat, po.lon];
    if (!ll[0] || !ll[1]) return;
    const label = poiName(id, po.name || id);
    // 開始/中継/終了で色分け
    const kind = (idx === 0) ? 'start' : (idx === n - 1 ? 'goal' : 'mid');
    const color =
      kind === 'start' ? '#2e7d32' :
      kind === 'goal'  ? '#c62828' :
                         '#1565c0';
    const badgeHtml = `
      <div class="stop-badge" style="background:${color}">
        ${idx+1}
      </div>
      <div class="stop-label">${label}</div>
    `;
    L.marker(ll, {
      zIndexOffset: 1000,
      icon: L.divIcon({
        className: 'stop-icon',
        html: badgeHtml,
        iconSize: [1,1],
        iconAnchor: [12, 18]
      })
    }).addTo(poiLayer);
  });

  // 2-2) 「順序外のPOI」は小さく
  pois.forEach(po => {
    if (orderMap.has(po.spot_id)) return; // すでに描いている
    const ll = [po.lat, po.lon];
    const label = poiName(po.spot_id, po.name || po.spot_id);
    L.marker(ll, {
      icon: L.divIcon({
        className: 'poi-icon',
        html: `<div class="poi-dot"></div><div class="poi-label">${label}</div>`,
        iconSize: [1,1], iconAnchor: [12,12],
      })
    }).addTo(poiLayer);
  });

  // 2-3) アクセスポイント
  (p.access_points || []).forEach(ap => {
    L.circleMarker([ap.lat, ap.lon], {
      radius: 4, color:'#555', fillColor:'#999', fillOpacity:0.9
    }).addTo(apLayer);
  });

  // 3) ビューポート
  const bounds = routeGroup.getLayers().reduce((b, lyr) => {
    try { return b.extend(lyr.getBounds()); } catch { return b; }
  }, L.latLngBounds([]));
  // ルートが薄いときのフォールバック：順序スポットで extent
  if (!bounds.isValid() && order.length) {
    const tmp = L.latLngBounds([]);
    order.forEach(id => {
      const po = pois.find(x => x.spot_id === id);
      if (po?.lat && po?.lon) tmp.extend([po.lat, po.lon]);
    });
    if (tmp.isValid()) map.fitBounds(tmp.pad(0.1));
  } else if (bounds.isValid()) {
    map.fitBounds(bounds.pad(0.06));
  }
}

// ---------- 現在地 & 近接再生 ----------
function currentRadius(lat, lon, p) {
  if (!Array.isArray(p.polyline) || p.polyline.length === 0) return 300;
  const latlngs = toLatLngs(p.polyline);
  const idx = nearestVertexIdx(lat, lon, latlngs);
  const mode = nearestIdxToMode[idx] || 'car';
  return mode === 'foot' ? 10 : 300;
}
async function maybePlay(lat, lon, p) {
  const assets = p.assets || [];
  const pois = p.along_pois || p.pois || [];
  if (!assets.length || !pois.length) return;
  const r = currentRadius(lat, lon, p);
  for (const po of pois) {
    if (played.has(po.spot_id)) continue;
    const d = hav([lat,lon], [po.lat, po.lon]);
    if (d <= r) {
      const asset = assets.find(a => a.spot_id === po.spot_id && a.audio?.url);
      if (asset?.audio?.url) {
        try {
          const a = new Audio(asset.audio.url);
          a.preload = 'auto';
          await a.play();
          played.add(po.spot_id);
          L.popup({ autoClose:true, closeButton:false })
            .setLatLng([po.lat, po.lon])
            .setContent(`▶️ ${poiName(po.spot_id, po.name || po.spot_id)}`)
            .openOn(map);
        } catch {}
      }
      break;
    }
  }
}
function startGeolocation() {
  if (!navigator.geolocation) return;
  watchId = navigator.geolocation.watchPosition(
    async pos => {
      const { latitude:lat, longitude:lon } = pos.coords;
      const ll = [lat, lon];
      if (!here) {
        here = L.circleMarker(ll, {
          radius: 6, color:'#1976d2', fillColor:'#42a5f5', fillOpacity:0.9
        }).addTo(map);
      } else {
        here.setLatLng(ll);
      }
      await maybePlay(lat, lon, props.plan);
    },
    () => {}, { enableHighAccuracy:true, maximumAge:5000, timeout:20000 }
  );
}

onMounted(async () => {
  ensureMap();
  await loadPoisDict();
  drawPlan(props.plan);
  startGeolocation();
  await nextTick(); map && map.invalidateSize();
});
onBeforeUnmount(() => {
  if (watchId != null && navigator.geolocation) {
    try { navigator.geolocation.clearWatch(watchId); } catch {}
  }
});
watch(() => [props.plan, props.lang], async () => {
  await loadPoisDict();
  drawPlan(props.plan);
});
</script>

<style scoped>
.map { width:100%; height: calc(100vh - 48px); }

/* 順序付きスポットの大バッジ */
.stop-icon { position: relative; white-space: nowrap; filter: drop-shadow(0 2px 2px rgba(0,0,0,.25)); }
.stop-badge {
  display:inline-flex; align-items:center; justify-content:center;
  width:28px; height:28px; border-radius:50%;
  color:#fff; font-weight:700; font-size:14px; margin-right:6px;
  border:2px solid #fff;
}
.stop-label {
  display:inline-block; background:#fff; border:1px solid #ddd;
  padding:3px 8px; border-radius:8px; font-size:12px; transform: translateY(-4px);
}

/* その他POI */
.poi-icon { position: relative; white-space: nowrap; }
.poi-dot { width:10px; height:10px; border-radius:50%; background:#1976d2;
  border:2px solid #fff; box-shadow:0 0 2px rgba(0,0,0,.3); }
.poi-label { transform: translate(12px, -10px); background:#fff; border:1px solid #ddd;
  padding:2px 6px; border-radius:6px; font-size:12px; }

/* 徒歩線の視認性アップ（影） */
:deep(.seg-foot) { filter: drop-shadow(0 0 2px rgba(0,0,0,.35)); }
</style>
