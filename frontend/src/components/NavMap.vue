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

// -- 地図タイルの定義 (変更なし) --
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
let poiMarkers = []; // マーカーの配列 (変更なし)

const flyToSpot = (lat, lon) => { // (変更なし)
  if (map.value) {
    map.value.flyTo([lat, lon], 16, {
      animate: true,
      duration: 1,
    });
  }
};
defineExpose({ flyToSpot }); // (変更なし)


// ===========================================
// ★★★ ここから drawRoute 関数を修正 ★★★
// ===========================================
const drawRoute = () => {
  if (routeLayer) {
    map.value.removeLayer(routeLayer);
  }
  if (props.plan && props.plan.route) {

    // GeoJSONのフィーチャー(セグメント)ごとにスタイルを動的に決定する関数
    const styleFunction = (feature) => {
      const mode = feature?.properties?.mode;
      
      if (mode === 'car') {
        // 車ルートのスタイル
        return {
          color: '#007bff',  // 青色
          weight: 5,
          opacity: 0.7,
        };
      } 
      else if (mode === 'foot') {
        // 徒歩ルートのスタイル
        return {
          color: '#ff8c00',  // オレンジ色
          weight: 4,
          opacity: 0.8,
          dashArray: '5, 10', // 破線
        };
      }
      
      // フォールバック (万が一 mode がない場合など)
      return { 
        color: '#ff0000', // 元の赤色
        weight: 5,
        opacity: 0.7,
      };
    };

    // L.geoJSON の style オプションに静的オブジェクトではなく、上記で定義した関数を渡す
    routeLayer = L.geoJSON(props.plan.route, {
      style: styleFunction, // ★修正点
    }).addTo(map.value);

    map.value.fitBounds(routeLayer.getBounds());
  }
};
// ===========================================
// ★★★ drawRoute 関数の修正ここまで ★★★
// ===========================================


const drawPois = () => { // (変更なし: waypoints_info と along_pois を描画)
  // 1. 以前のマーカーをすべてクリア
  poiMarkers.forEach(marker => map.value.removeLayer(marker));
  poiMarkers = [];

  if (!props.plan) return;

  // 2. マーカーを追加する内部ヘルパー関数を定義
  const addPoiMarker = (poi) => {
    // lat/lon がないデータはスキップ
    if (!poi || typeof poi.lat !== 'number' || typeof poi.lon !== 'number') {
      return;
    }
    const marker = L.marker([poi.lat, poi.lon]).addTo(map.value)
      .bindPopup(`<b>${poi.name}</b>`); 
    poiMarkers.push(marker);
  };

  // 3. 「周遊スポット (Waypoints)」を描画
  if (props.plan.waypoints_info) {
    props.plan.waypoints_info.forEach(addPoiMarker);
  }

  // 4. 「周辺のスポット (AlongPOIs)」も描画
  if (props.plan.along_pois) {
    props.plan.along_pois.forEach(addPoiMarker);
  }
};


const setupMap = () => { // (変更なし)
  if (mapContainer.value && !map.value) {
    map.value = L.map(mapContainer.value).setView([39.145, 140.102], 10);

    const baseMaps = {
      "地理院地図 標準": gsiStd,
      "地理院地図 淡色": gsiOpt,
    };
    gsiStd.addTo(map.value);
    L.control.layers(baseMaps).addTo(map.value);
    L.control.scale({ imperial: false, metric: true }).addTo(map.value);

    drawRoute(); // 修正されたdrawRouteが呼ばれる
    drawPois();
    startTracking();
  }
};

const updateUserLocation = (lat, lng) => { // (変更なし)
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

const startTracking = () => { // (変更なし)
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

onMounted(() => { // (変更なし)
  setupMap();
});

onBeforeUnmount(() => { // (変更なし)
  if (map.value) {
    map.value.remove();
    map.value = null;
  }
});

watch(() => props.plan, () => { // (変更なし)
  if (map.value) {
    drawRoute(); // 修正されたdrawRouteが呼ばれる
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