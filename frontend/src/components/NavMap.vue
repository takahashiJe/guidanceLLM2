<!-- src/components/NavMap.vue -->
<template>
  <div ref="mapEl" class="map"></div>
</template>

<script setup>
import { onMounted, watch, ref } from 'vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const props = defineProps({
  plan: { type: Object, default: null },
});

const mapEl = ref(null);
let map, routeLayer, here;

function ensureMap() {
  if (map) return;
  map = L.map(mapEl.value, { zoomControl: false });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map);
}

function drawPlan(plan) {
  if (!map) return;
  if (routeLayer) {
    routeLayer.remove();
    routeLayer = null;
  }
  if (!plan?.route) return;
  routeLayer = L.geoJSON(plan.route).addTo(map);
  try {
    const b = routeLayer.getBounds();
    if (b.isValid()) map.fitBounds(b, { padding: [20, 20] });
  } catch {}
}

function trackHere() {
  if (!map) return;
  if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        const latlng = [latitude, longitude];
        if (!here) {
          here = L.circleMarker(latlng, { radius: 6 }).addTo(map);
        } else {
          here.setLatLng(latlng);
        }
      },
      () => {}, { enableHighAccuracy: true }
    );
  }
}

onMounted(() => {
  ensureMap();
  drawPlan(props.plan);
  trackHere();
});

watch(() => props.plan, (p) => drawPlan(p), { deep: true });
</script>

<style scoped>
.map { width:100%; height:100%; }
</style>
