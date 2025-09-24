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

const gsiStd = L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png', {
  attribution: "<a href='https://maps.gsi.go.jp/development/ichiran.html' target='_blank'>地理院タイル</a>",
});
const gsiOpt = L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png', {
  attribution: "<a href='https://maps.gsi.go.jp/development/ichiran.html' target='_blank'>地理院タイル</a>",
});

const props = defineProps({
  plan: {
    type: Object,
    required: true,
  },
  // NavViewから現在地情報を受け取るためのprop
  currentPos: {
    type: Object,
    default: null,
  }
});

const mapContainer = ref(null);
const map = ref(null);
const userLocationMarker = ref(null); // ★ ref() でラップ
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

// ===========================================
// ★★★ ここからが修正箇所です ★★★
// ===========================================

// NavViewから渡された座標でマーカーを更新する関数
const updateCurrentPosition = (lat, lng) => {
  if (!map.value) return;
  const latlng = L.latLng(lat, lng);

  if (userLocationMarker.value) {
    // 既存マーカーの位置を更新
    userLocationMarker.value.setLatLng(latlng);
  } else {
    // マーカーがまだなければ作成
    userLocationMarker.value = L.marker(latlng, {
      icon: L.divIcon({
        className: 'current-position-marker',
        html: '<div class="pulse"></div>',
        iconSize: [20, 20],
      }),
    }).addTo(map.value);
  }
};

// 親コンポーネントから呼び出せるように関数を公開
defineExpose({ 
  flyToSpot,
  updateCurrentPosition // この関数を公開
});

// ===========================================
// ★★★ 修正箇所はここまで ★★★
// ===========================================

const drawRoute = () => {
  if (routeLayer) {
    map.value.removeLayer(routeLayer);
  }
  if (props.plan && props.plan.route) {
    const styleFunction = (feature) => {
      const mode = feature?.properties?.mode;
      if (mode === 'car') return { color: '#007bff', weight: 5, opacity: 0.7 };
      if (mode === 'foot') return { color: '#ff8c00', weight: 4, opacity: 0.8, dashArray: '5, 10' };
      return { color: '#ff0000', weight: 5, opacity: 0.7 };
    };
    routeLayer = L.geoJSON(props.plan.route, { style: styleFunction }).addTo(map.value);
    map.value.fitBounds(routeLayer.getBounds());
  }
};

const drawPois = () => {
  poiMarkers.forEach(marker => map.value.removeLayer(marker));
  poiMarkers = [];
  if (!props.plan) return;

  const addPoiMarker = (poi) => {
    if (!poi || typeof poi.lat !== 'number' || typeof poi.lon !== 'number') return;
    const marker = L.marker([poi.lat, poi.lon]).addTo(map.value).bindPopup(`<b>${poi.name}</b>`);
    poiMarkers.push(marker);
  };

  if (props.plan.waypoints_info) props.plan.waypoints_info.forEach(addPoiMarker);
  if (props.plan.along_pois) props.plan.along_pois.forEach(addPoiMarker);
};

const setupMap = () => {
  if (mapContainer.value && !map.value) {
    map.value = L.map(mapContainer.value).setView([39.145, 140.102], 10);
    const baseMaps = { "地理院地図 標準": gsiStd, "地理院地図 淡色": gsiOpt };
    gsiStd.addTo(map.value);
    L.control.layers(baseMaps).addTo(map.value);
    L.control.scale({ imperial: false, metric: true }).addTo(map.value);

    drawRoute();
    drawPois();
    
    // ★★★ デバッグ中はNavViewから位置情報を受け取るため、ここでの位置情報追跡は不要
    // startTracking();
  }
};

/*
// ★ このコンポーネント自身での位置情報追跡は不要になるためコメントアウト
const startTracking = () => {
  if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        updateCurrentPosition(latitude, longitude); // 修正後の関数を呼ぶ
      },
      (error) => { console.error('Geolocation error:', error); },
      { enableHighAccuracy: true }
    );
  } else {
    console.error('Geolocation is not supported by this browser.');
  }
};
*/

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

<style>
/* scopedを外してグローバルに適用 */
.map-container {
  width: 100%;
  height: 100%;
}

/* 現在地マーカーのスタイル */
.current-position-marker .pulse {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #007bff;
  border: 2px solid #fff;
  box-shadow: 0 0 0 rgba(0, 123, 255, 0.4);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(0, 123, 255, 0.7);
  }
  70% {
    transform: scale(1);
    box-shadow: 0 0 0 10px rgba(0, 123, 255, 0);
  }
  100% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(0, 123, 255, 0);
  }
}
</style>