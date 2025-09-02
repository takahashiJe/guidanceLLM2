<template>
  <div class="page navigator">
    <div ref="mapEl" class="map"></div>

    <div class="bottom-sheet">
      <div class="now">
        <div class="title">次の案内</div>
        <div class="text">{{ nextText }}</div>
      </div>
      <div class="controls">
        <button @click="playCurrent" class="btn">▶ 再生</button>
        <button @click="pause" class="btn">⏸ 停止</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, computed, onBeforeUnmount } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useRoute } from "vue-router";
import { usePlanStore } from "@/stores/plan";
import { useGeoStore } from "@/stores/geo";
import { useNavStore } from "@/stores/nav";

// 簡易再生（必要ならWebAudioに差し替え）
let audio = new Audio();

const route = useRoute();
const planStore = usePlanStore();
const geoStore = useGeoStore();
const navStore = useNavStore();

const mapEl = ref(null);
let map, routeLayer, me;

const nextText = computed(() => {
  if (!planStore.plan) return "";
  // 最初のアセットのテキストをとりあえず表示（本実装では近接順）
  const a = (planStore.plan.assets || [])[0];
  return a ? a.text : "";
});

onMounted(async () => {
  // Plan の復元はルートガードで済んでいる想定
  initMap();
  drawRoute();
  geoStore.startWatch();
});

onBeforeUnmount(() => {
  geoStore.stopWatch();
});

function initMap() {
  map = L.map(mapEl.value).setView([39.2, 139.9], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
  me = L.marker([39.2, 139.9]).addTo(map).bindTooltip("現在地");
}

function drawRoute() {
  if (!planStore.plan) return;
  if (routeLayer) routeLayer.remove();
  routeLayer = L.geoJSON(planStore.plan.route).addTo(map);
  const b = routeLayer.getBounds();
  if (b.isValid()) map.fitBounds(b, { padding: [40, 40] });
}

// 近接トリガ（非常に単純な距離判定の骨組み）
function checkProximity() {
  if (!planStore.plan || !geoStore.position) return;
  const pos = geoStore.position;
  me.setLatLng([pos.lat, pos.lon]);
  const pois = planStore.plan.along_pois || [];
  const thCar = 220, thFoot = 30;

  for (const poi of pois) {
    if (navStore.triggeredSpotIds.has(poi.spot_id)) continue;
    const d = distanceMeters(pos.lat, pos.lon, poi.lat, poi.lon);
    const th = poi.source_segment_mode === "car" ? thCar : thFoot;
    if (d <= th) {
      navStore.markTriggered(poi.spot_id);
      playBySpot(poi.spot_id);
      break;
    }
  }
}

function distanceMeters(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = (n) => (n * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// 位置更新を監視
watchEffectLoop();
function watchEffectLoop() {
  const i = setInterval(checkProximity, 1500); // 簡易ループ（後で最適化）
  window.addEventListener("beforeunload", () => clearInterval(i));
}

function playBySpot(spotId) {
  const asset = (planStore.plan.assets || []).find((a) => a.spot_id === spotId);
  if (!asset) return;
  audio.pause();
  audio = new Audio(asset.audio.url);
  audio.play().catch(() => {});
  navStore.setNowPlaying(spotId);
}

function playCurrent() {
  const a = (planStore.plan.assets || [])[0];
  if (!a) return;
  audio.pause();
  audio = new Audio(a.audio.url);
  audio.play().catch(() => {});
}
function pause() {
  audio.pause();
}
</script>

<style scoped>
.page { position: relative; min-height: 100vh; background: #0e0f12; }
.map { position: absolute; inset: 0; }
.bottom-sheet {
  position: absolute; left: 0; right: 0; bottom: 0;
  background: rgba(14,15,18,0.92); color: #fff;
  border-top-left-radius: 20px; border-top-right-radius: 20px;
  padding: 12px 14px; box-shadow: 0 -6px 24px rgba(0,0,0,0.3);
}
.now .title { font-weight: 700; margin-bottom: 4px; }
.controls { display: flex; gap: 8px; margin-top: 8px; }
.btn { flex: 1; padding: 12px; border: none; border-radius: 12px; background: #3b82f6; color: #fff; font-weight: 700; }
</style>
