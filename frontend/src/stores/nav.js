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
    waypoints,
    alongPois,
    focusedWaypoint,
    setPlan,
    focusOnWaypointById,
    reset,
  }
})