import { ref, computed, readonly } from 'vue'
import { defineStore } from 'pinia'

export const useNavStore = defineStore('nav', () => {
  // --- State ---
  // プラン作成中に使用する一時的なデータ
  const lang = ref('ja')
  const origin = ref({ lat: 39.72, lon: 140.13 }) // 秋田県庁の座標をデフォルトに
  const waypointsByIds = ref([]) // 選択されたspot_idの配列

  // ナビゲーション開始後にセットされるデータ
  const plan = ref(null)
  const focusedWaypointIndex = ref(0)

  // --- Getters ---
  const waypoints = computed(() => plan.value?.waypoints || [])
  const alongPois = computed(() => plan.value?.along_pois || [])

  const focusedWaypoint = computed(() => {
    if (!plan.value || !waypoints.value.length) return null
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
    focusedWaypointIndex.value = 0
  }

  function focusNextWaypoint() {
    if (!plan.value || !waypoints.value.length) return;
    focusedWaypointIndex.value = (focusedWaypointIndex.value + 1) % waypoints.value.length;
  }

  function reset() {
    plan.value = null
    focusedWaypointIndex.value = 0
    waypointsByIds.value = []
  }

  return {
    // PlanView用
    lang,
    origin,
    waypointsByIds,
    setLang,
    setOrigin,
    setWaypointsByIds,

    // NavView用
    plan: readonly(plan),
    waypoints,
    alongPois,
    focusedWaypoint,
    setPlan,
    focusNextWaypoint,
    reset,
  }
})