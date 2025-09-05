<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Leafletのデフォルトアイコンパスの問題を修正
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

const props = defineProps({
  routeGeojson: {
    type: Object,
    required: true
  },
  pois: {
    type: Array,
    default: () => []
  }
});

const mapContainer = ref(null);
let map = null;
let routeLayer = null;

onMounted(() => {
  if (!mapContainer.value) return;

  map = L.map(mapContainer.value);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  drawRoute();
  drawPois();
});

onUnmounted(() => {
  if (map) {
    map.remove();
    map = null;
  }
});

const drawRoute = () => {
  if (!map || !props.routeGeojson) return;
  if (routeLayer) map.removeLayer(routeLayer);

  routeLayer = L.geoJSON(props.routeGeojson, {
    style: (feature) => {
      const color = feature.properties.mode === 'car' ? '#007bff' : '#28a745';
      return { color, weight: 5, opacity: 0.8 };
    }
  }).addTo(map);

  map.fitBounds(routeLayer.getBounds(), { padding: [20, 20] });
};

const drawPois = () => {
  if (!map || !props.pois) return;
  props.pois.forEach(poi => {
    if (poi.lonlat) {
      L.marker([poi.lonlat[1], poi.lonlat[0]])
        .addTo(map)
        .bindPopup(`<b>${poi.name?.ja || poi.spot_id}</b>`);
    }
  });
};

// 親コンポーネントからこのメソッドを呼び出せるようにする
defineExpose({
  flyTo: (coords, zoom = 15) => {
    if (map && coords) {
      // Leafletは [lat, lon] の順
      map.flyTo([coords[1], coords[0]], zoom);
    }
  }
});
</script>

<template>
  <div ref="mapContainer" class="map-container"></div>
</template>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  background-color: #f0f0f0;
}
</style>