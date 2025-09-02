<template>
  <div class="h-full w-full relative bg-white">
    <div ref="mapEl" class="absolute inset-0"></div>

    <!-- ボトムシート風カード -->
    <div class="absolute inset-x-0 bottom-0">
      <div class="mx-auto max-w-screen-sm">
        <div class="m-3 rounded-2xl bg-white shadow-lg p-3">
          <div class="flex items-center justify-between">
            <div class="text-sm text-gray-500">次の案内</div>
            <button class="text-sm text-blue-600" @click="toggleMute">{{ muted ? 'ミュート解除' : 'ミュート' }}</button>
          </div>
          <div class="mt-1 font-medium line-clamp-2">{{ nextText || 'スポットに近づくと案内します' }}</div>
          <div class="mt-2 flex items-center gap-2 text-sm text-gray-500">
            <span>再生済:</span><span>{{ playedCount }}</span>
            <span class="ml-3">リルート:</span><span>{{ reroutes }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="absolute top-3 left-1/2 -translate-x-1/2 px-2 py-1 text-xs bg-black/70 text-white rounded-full">
      オフライン案内中
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { usePlanStore } from "@/stores/planStore";
import { useNavStore } from "@/stores/navStore";

const mapEl = ref(null);
let map;
let routeLayer = null;
let meMarker = null;

const store = usePlanStore();
const nav = useNavStore();

const muted = ref(false);
const nextText = ref("");

const playedCount = computed(() => nav.played.size);
const reroutes = computed(() => nav.reroutes);

function toggleMute(){ muted.value = !muted.value; }

function nearestPoi(lat, lon) {
  const plan = store.current;
  if (!plan) return null;
  const carTh = 200, footTh = 30;
  for (const poi of plan.along_pois || []) {
    if (nav.played.has(poi.spot_id)) continue;
    const d = L.latLng(poi.lat, poi.lon).distanceTo(L.latLng(lat, lon));
    const th = poi.source_segment_mode === "foot" ? footTh : carTh;
    if (d < th) return poi;
  }
  return null;
}

async function speak(spot_id) {
  const plan = store.current;
  const asset = (plan.assets || []).find(a => a.spot_id === spot_id);
  const text = asset?.text || "";
  if (!asset) return;
  nextText.value = text;
  if (!muted.value) {
    const audio = new Audio(asset.audio.url); // 相対 /packs/...
    try { await audio.play(); } catch {}
  }
  nav.markPlayed(spot_id);
}

onMounted(async () => {
  const plan = store.current;
  if (!plan) return;

  map = L.map(mapEl.value).setView([plan.polyline[0][1], plan.polyline[0][0]], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);

  routeLayer && routeLayer.remove();
  routeLayer = L.geoJSON(plan.route).addTo(map);

  navigator.geolocation.watchPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;

      if (!meMarker) {
        meMarker = L.marker([latitude, longitude]).addTo(map);
      } else {
        meMarker.setLatLng([latitude, longitude]);
      }

      const hit = nearestPoi(latitude, longitude);
      if (hit) speak(hit.spot_id);
    },
    () => {},
    { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 }
  );
});
</script>

<style scoped>
/* 既存UIのトーンに合わせた軽いカード表現 */
</style>
