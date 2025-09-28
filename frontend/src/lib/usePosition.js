import { ref, onMounted, onUnmounted } from 'vue';
import { calculateDistance } from './geoutils';

// 本番用: ブラウザのGeolocation APIを使用する
export function usePosition() {
  const currentPos = ref(null);
  // ダミー（isDebug=falseのためUIに出ないが、型合わせで返しておく）
  const debugLat = ref(null);
  const debugLng = ref(null);
  const following = ref(false);

  let watchId = null;
  let restartTimerId = null;
  let lastAcceptedPos = null;

  const MIN_MOVE_METERS = 10; // GPSの微小な揺れを吸収するための閾値

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
        const nextPos = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        };

        if (lastAcceptedPos) {
          const delta = calculateDistance(lastAcceptedPos, nextPos);
          if (delta < MIN_MOVE_METERS) {
            return;
          }
        }

        currentPos.value = nextPos;
        lastAcceptedPos = nextPos;
      },
      (err) => {
        console.error('Geolocation error:', err);

        if (err?.code === 3) {
          // TIMEOUT: 位置が取得できなかった場合はウォッチを再起動して再トライ
          scheduleRestart();
          return;
        }

        currentPos.value = null; // それ以外のエラー時はnullにする
        lastAcceptedPos = null;
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
    lastAcceptedPos = null;
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
