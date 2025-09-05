<template>
  <div ref="mapContainer" class="map-container"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Leafletのデフォルトアイコン問題を修正
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

// -- 修正点: 地図タイルの定義をコンポーネント内に記述 --
const gsiStd = L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png', {
  attribution: "<a href='https://maps.gsi.go.jp/development/ichiran.html' target='_blank'>地理院タイル</a>",
});
const gsiOpt = L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png', {
  attribution: "<a href='https://maps.gsi.go.jp/development/ichiran.html' target='_blank'>地理院タイル</a>",
});
// -- ここまで --

const props = defineProps({
  plan: {
    type: Object,
    required: true,
  },
});

const mapContainer = ref(null);
const map = ref(null);
let userLocationMarker = null;
let routeLayer = null;
let poiMarkers = [];

const flyToSpot = (lat, lon) => {
  if (map.value) {
    map.value.flyTo([lat, lon], 16, {
      animate: true,
      duration: 1,
    });
  }
};
defineExpose({ flyToSpot });


const drawRoute = () => {
  if (routeLayer) {
    map.value.removeLayer(routeLayer);
  }
  if (props.plan && props.plan.route) {
    routeLayer = L.geoJSON(props.plan.route, {
      style: {
        color: '#ff0000',
        weight: 5,
        opacity: 0.7,
      },
    }).addTo(map.value);
    map.value.fitBounds(routeLayer.getBounds());
  }
};

const drawPois = () => {
  poiMarkers.forEach(marker => map.value.removeLayer(marker));
  poiMarkers = [];

  if (props.plan && props.plan.along_pois) {
    props.plan.along_pois.forEach(poi => {
      const marker = L.marker([poi.lat, poi.lon]).addTo(map.value)
        .bindPopup(`<b>${poi.name}</b><br>${poi.description || ''}`);
      poiMarkers.push(marker);
    });
  }
};

const setupMap = () => {
  if (mapContainer.value && !map.value) {
    map.value = L.map(mapContainer.value).setView([39.145, 140.102], 10);

    const baseMaps = {
      "地理院地図 標準": gsiStd,
      "地理院地図 淡色": gsiOpt,
    };
    gsiStd.addTo(map.value);
    L.control.layers(baseMaps).addTo(map.value);
    L.control.scale({ imperial: false, metric: true }).addTo(map.value);

    drawRoute();
    drawPois();
    startTracking();
  }
};

const updateUserLocation = (lat, lng) => {
  if (!map.value) return;
  const latlng = L.latLng(lat, lng);
  if (userLocationMarker) {
    userLocationMarker.setLatLng(latlng);
  } else {
    userLocationMarker = L.circleMarker(latlng, {
      radius: 8,
      color: '#ffffff',
      weight: 2,
      fillColor: '#007bff',
      fillOpacity: 1,
    }).addTo(map.value);
  }
};

const startTracking = () => {
  if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        updateUserLocation(latitude, longitude);
      },
      (error) => {
        console.error('Geolocation error:', error);
      },
      {
        enableHighAccuracy: true,
      }
    );
  } else {
    console.error('Geolocation is not supported by this browser.');
  }
};

onMounted(() => {
  setupMap();
});

onBeforeUnmount(() => {
  if (map.value) {
    map.value.remove();
    map.value = null;
  }
});

watch(() => props.plan, () => {
  if (map.value) {
    drawRoute();
    drawPois();
  }
}, { deep: true });
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
}
</style>