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

const TILE_URL_TEMPLATE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';

const esriWorldStreet = L.tileLayer(
  TILE_URL_TEMPLATE,
  {
    attribution:
      "Tiles &copy; Esri — Source: Esri, HERE, Garmin, FAO, NOAA, USGS, EPA, NPS",
    maxZoom: 19
  }
);

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

const emit = defineEmits(['user-pan']);

const mapContainer = ref(null);
const map = ref(null);
const userLocationMarker = ref(null); // ★ ref() でラップ
let routeLayer = null;
let poiMarkers = [];
let isProgrammaticMove = false;
let programmaticResetTimer = null;

const scheduleProgrammaticReset = (delay = 800) => {
  if (programmaticResetTimer) {
    clearTimeout(programmaticResetTimer);
    programmaticResetTimer = null;
  }
  programmaticResetTimer = window.setTimeout(() => {
    isProgrammaticMove = false;
    programmaticResetTimer = null;
  }, delay);
};

const markProgrammaticMove = (delay = 800) => {
  isProgrammaticMove = true;
  scheduleProgrammaticReset(delay);
};

const flyToSpot = (lat, lon, zoom = undefined, flyOptions = {}) => {
  if (!map.value) return;
  let targetZoom;
  if (typeof zoom === 'number') {
    targetZoom = zoom;
  } else if (zoom === null) {
    targetZoom = map.value.getZoom();
  } else {
    targetZoom = 16;
  }
  markProgrammaticMove(Math.max(800, (flyOptions.duration ?? 1) * 1200));
  map.value.flyTo([lat, lon], targetZoom, {
    animate: true,
    duration: 1,
    ...flyOptions,
  });
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
    markProgrammaticMove();
    map.value.fitBounds(routeLayer.getBounds());
  }
};

const drawPois = () => {
  poiMarkers.forEach(marker => map.value.removeLayer(marker));
  poiMarkers = [];
  if (!props.plan) return;

  const addPoiMarker = (poi) => {
    if (!poi || typeof poi.lat !== 'number' || typeof poi.lon !== 'number') return;
    const marker = L.marker([poi.lat, poi.lon], {
      interactive: false,
    }).addTo(map.value);
    poiMarkers.push(marker);
  };

  if (props.plan.waypoints_info) props.plan.waypoints_info.forEach(addPoiMarker);
  if (props.plan.along_pois) props.plan.along_pois.forEach(addPoiMarker);
};

const setupMap = () => {
  if (mapContainer.value && !map.value) {
    map.value = L.map(mapContainer.value, { zoomControl: false });
    markProgrammaticMove();
    map.value.setView([39.145, 140.102], 10);
    esriWorldStreet.addTo(map.value);
    L.control.scale({ imperial: false, metric: true }).addTo(map.value);
    if (map.value.attributionControl) {
      map.value.attributionControl.setPrefix('');
    }

    map.value.on('movestart', () => {
      if (!isProgrammaticMove) {
        emit('user-pan');
      }
    });

    map.value.on('moveend', () => {
      if (isProgrammaticMove) {
        esriWorldStreet.setUrl(TILE_URL_TEMPLATE);
      }
      scheduleProgrammaticReset(200);
    });

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
  if (programmaticResetTimer) {
    clearTimeout(programmaticResetTimer);
    programmaticResetTimer = null;
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

.leaflet-control-attribution {
  font-size: 0.7rem;
  padding: 3px 8px;
  background: rgba(15, 23, 42, 0.65);
  color: #e2e8f0;
  border-radius: 999px;
  box-shadow: 0 8px 14px rgba(15, 23, 42, 0.25);
  line-height: 1.2;
}

.leaflet-control-attribution a {
  color: rgba(148, 197, 255, 0.85);
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
