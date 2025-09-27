import { ref, onMounted, onUnmounted } from 'vue';

// 本番用: ブラウザのGeolocation APIを使用する
export function usePosition() {
  const currentPos = ref(null);
  // ダミー（isDebug=falseのためUIに出ないが、型合わせで返しておく）
  const debugLat = ref(null);
  const debugLng = ref(null);
  const following = ref(false);

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
      watchId = null;
    }
  });

  // 本番では isMock:false
  const isMock = false;

  // デバッグ用関数は no-op で返す（参照されても害がない）
  const setDebugPos = () => {};
  const toggleFollowing = () => {};

  return {
    isMock,
    currentPos,
    debugLat,
    debugLng,
    following,
    setDebugPos,
    toggleFollowing,
  };
}