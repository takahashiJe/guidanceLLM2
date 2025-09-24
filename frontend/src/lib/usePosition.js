import { ref, onMounted, onUnmounted } from 'vue';

// 本番用: ブラウザのGeolocation APIを使用する
export function usePosition() {
  const currentPos = ref(null);
  let watchId = null;

  onMounted(() => {
    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        currentPos.value = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        };
      },
      (err) => {
        console.error('Geolocation error:', err);
        currentPos.value = null; // エラー時はnullにする
      },
      {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  });

  onUnmounted(() => {
    if (watchId !== null) {
      navigator.geolocation.clearWatch(watchId);
    }
  });

  return { currentPos };
}