// src/stores/nav.js

import { ref, computed, readonly } from 'vue'
import { defineStore } from 'pinia'

export const useNavStore = defineStore('nav', () => {
  // --- State ---
  const lang = ref('ja')
  const origin = ref(null) // ★ デフォルト値を削除し、nullで初期化
  const waypointsByIds = ref([])

  const plan = ref(null)
  const focusedWaypointIndex = ref(0) 

  // --- Getters ---
  
  // 'waypoints' ゲッターは、バックエンドから返される計算済みの「主要訪問先」リスト (waypoints_info) を参照するように変更します。
  const waypoints = computed(() => plan.value?.waypoints_info || [])

  // 'alongPois' ゲッターは、バックエンドから返される「純粋な沿道スポット」リスト (along_pois) を参照します (これは元のままで正しいです)。
  const alongPois = computed(() => plan.value?.along_pois || [])

  const focusedWaypoint = computed(() => {
    if (!plan.value || !waypoints.value.length) return null
    // 'waypoints' ゲッターが waypoints_info を指すようになったため、ここは自動的に正しく動作します。
    return waypoints.value[focusedWaypointIndex.value] || null
  })

  // --- Actions ---
  function setLang(newLang) {
    lang.value = newLang
  }

  function setOrigin(newOrigin) {
    if (newOrigin && typeof newOrigin.lat === 'number' && typeof newOrigin.lon === 'number') {
      origin.value = newOrigin
    }
  }

  function setWaypointsByIds(ids) {
    waypointsByIds.value = ids
  }

  function setPlan(newPlan) {
    plan.value = newPlan
    // 新しいプランがセットされたことをデバッグログに出力
    console.log('[NavStore] New plan set:', newPlan); 
    focusedWaypointIndex.value = 0
  }

  // 'focusOnWaypointById' が参照するリスト (waypoints.value) が 
  //       waypoints_info を指すようになったため、ロジック自体はこれで正常に動作します。
  function focusOnWaypointById(spotId) {
    if (!plan.value || !waypoints.value.length) return;
    const index = waypoints.value.findIndex(wp => wp.spot_id === spotId);
    if (index !== -1) {
      focusedWaypointIndex.value = index;
    }
  }
  
  function reset() {
    plan.value = null
    focusedWaypointIndex.value = 0
    waypointsByIds.value = []
  }

  return {
    lang,
    origin,
    waypointsByIds,
    setLang,
    setOrigin,
    setWaypointsByIds,
    plan: readonly(plan),
    waypoints, // <-- これは 'waypoints_info' を返します
    alongPois, // <-- これは 'along_pois' (純粋な沿道) を返します
    focusedWaypoint,
    setPlan,
    focusOnWaypointById,
    reset,
  }
  // , { // <--- 第3引数を追加
  //   persist: true,
  // }
})