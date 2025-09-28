import { ref, onMounted, onUnmounted } from 'vue';

// 本番用: ブラウザのGeolocation APIを使用する
export function usePosition() {
  const currentPos = ref(null);
  // ダミー（isDebug=falseのためUIに出ないが、型合わせで返しておく）
  const debugLat = ref(null);
  const debugLng = ref(null);
  const following = ref(false);

  let watchId = null;
  let restartTimerId = null;

  const clearWatch = () => {
    if (watchId !== null) {
      navigator.geolocation.clearWatch(watchId);
      watchId = null;
    }
  };

  const scheduleRestart = () => {
    if (restartTimerId) {
      clearTimeout(restartTimerId);
    }
    restartTimerId = window.setTimeout(() => {
      restartTimerId = null;
      startWatch();
    }, 1000);
  };

  const startWatch = () => {
    if (!('geolocation' in navigator)) {
      console.warn('Geolocation API is not available in this environment.');
      return;
    }

    clearWatch();

    const watchOptions = {
      enableHighAccuracy: true,
      timeout: 30000,
      maximumAge: 15000,
    };

    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        currentPos.value = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        };
      },
      (err) => {
        console.error('Geolocation error:', err);

        if (err?.code === 3) {
          // TIMEOUT: 位置が取得できなかった場合はウォッチを再起動して再トライ
          scheduleRestart();
          return;
        }

        currentPos.value = null; // それ以外のエラー時はnullにする
      },
      watchOptions
    );
  };

  onMounted(() => {
    startWatch();
  });

  onUnmounted(() => {
    clearWatch();
    if (restartTimerId) {
      clearTimeout(restartTimerId);
      restartTimerId = null;
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
