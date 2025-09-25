// frontend/src/lib/usePosition.mock.js
import { ref, onMounted, onUnmounted } from 'vue';

/**
 * デバッグ用現在地フック
 * - 入力欄の lat/lng を「現在地」として扱う
 * - 「追従」ON中は同じ座標でも定期的に push して watch を発火
 * - NavView.vue 側の isDebug は isMock を参照
 */
export function usePosition() {
  // ★ ご指定のデフォルト座標
  const debugLat = ref(39.39347690860294);
  const debugLng = ref(140.07376949003486);

  // 現在地（NavViewが watch する）
  const currentPos = ref({ lat: debugLat.value, lng: debugLng.value });

  // 追従（ON の間は一定間隔で pushNow して watch を発火）
  const following = ref(true);
  let timerId = null;

  const pushNow = () => {
    const la = Number(debugLat.value);
    const ln = Number(debugLng.value);
    if (!Number.isFinite(la) || !Number.isFinite(ln)) return;
    currentPos.value = { lat: la, lng: ln };
  };

  const startFollowing = () => {
    if (timerId) return;
    timerId = window.setInterval(pushNow, 1000); // 1000msごとに現在値を push
  };

  const stopFollowing = () => {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
  };

  const toggleFollowing = () => {
    following.value = !following.value;
    if (following.value) startFollowing();
    else stopFollowing();
  };

  // 入力欄から渡された緯度経度をセット（即時反映）
  const setDebugPos = (lat, lng) => {
    const la = Number(lat);
    const ln = Number(lng);
    if (!Number.isFinite(la) || !Number.isFinite(ln)) {
      console.warn('[usePosition.mock] invalid coords', lat, lng);
      return;
    }
    debugLat.value = la;
    debugLng.value = ln;
    pushNow(); // 1回即時反映
  };

  onMounted(() => {
    pushNow();             // 初期反映
    if (following.value) { // 追従ONなら定期push開始
      startFollowing();
    }
  });

  onUnmounted(() => {
    stopFollowing();
  });

  return {
    // 本番/モック判定用フラグ
    isMock: true,

    // 実際に使うリアクティブ値と関数
    currentPos,
    debugLat,
    debugLng,
    following,
    setDebugPos,
    toggleFollowing,
  };
}
