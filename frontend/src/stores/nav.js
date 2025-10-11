import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useRouter } from 'vue-router'
import * as api from '@/lib/api'

import { getDeviceUUID } from '@/lib/uuid'

// 30分
const PLAN_TTL = 30 * 60 * 1000

const createRouteCacheKey = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try {
      return crypto.randomUUID()
    } catch {}
  }
  const rand = Math.random().toString(16).slice(2, 10)
  return `route-${Date.now()}-${rand}`
}

export const useNavStore = defineStore('nav', () => {
  const router = useRouter()

  // --- State ---
  const lang = ref('ja')
  const origin = ref(null)
  const waypointsByIds = ref([])
  const plan = ref(null)
  const isRouteLoading = ref(false)
  const isNavigating = ref(false) // This now represents the single, synchronous navigation plan generation step
  const error = ref(null)
  const deviceId = ref(null)

  // --- Getters ---
  const isRouteReady = computed(() => !!plan.value?.route)
  const isNavigationReady = computed(() => !!plan.value?.assets && plan.value.assets.length > 0)
  const waypoints = computed(() => plan.value?.waypoints_info || [])
  const alongPois = computed(() => plan.value?.along_pois || [])

  // --- Actions ---

  const reset = () => {
    console.log('[NavStore] Resetting navigation state...');
    lang.value = 'ja'
    origin.value = null
    waypointsByIds.value = []
    plan.value = null
    isRouteLoading.value = false
    isNavigating.value = false
    error.value = null
    console.log('[NavStore] Navigation state has been reset.');
  }

  const fetchRoute = async (planOptions, opts = {}) => {
    const { navigate = true } = opts
    reset()
    isRouteLoading.value = true
    error.value = null

    lang.value = planOptions.language
    origin.value = planOptions.origin
    waypointsByIds.value = planOptions.waypoints?.map((w) => w.spot_id) ?? []

    try {
      const routeData = await api.createRoutePlan(planOptions)

      plan.value = {
        planOptions,
        route: routeData.feature_collection,
        polyline: routeData.polyline,
        segments: routeData.segments,
        legs: routeData.legs,
        waypoints_info: routeData.waypoints_info,
        pack_id: null,
        along_pois: [],
        assets: [],
        manifest_url: null,
        createdAt: Date.now(),
        cacheKey: createRouteCacheKey(),
      }

      if (navigate) {
        router.push('/nav')
      }
    } catch (e) {
      console.error('Failed to fetch route', e)
      error.value = e.message || 'ルート計算に失敗しました'
    } finally {
      isRouteLoading.value = false
    }
  }

  const startGuidance = async () => {
    if (!isRouteReady.value || isNavigating.value) return
    
    isNavigating.value = true
    error.value = null
    try {
      const navRequestPayload = {
        language: lang.value,
        buffer: { car: 300, foot: 10 },
        route: plan.value.route,
        polyline: plan.value.polyline,
        segments: plan.value.segments,
        legs: plan.value.legs,
        waypoints_info: plan.value.waypoints_info,
      }

      // Call the new synchronous API function
      const navigationPlan = await api.createPlan(navRequestPayload)
      console.log('Navigation plan received:', navigationPlan)

      // Merge the navigation data into the existing plan
      plan.value = {
        ...plan.value,
        pack_id: navigationPlan.pack_id,
        along_pois: navigationPlan.along_pois,
        assets: navigationPlan.assets,
        manifest_url: navigationPlan.manifest_url,
        createdAt: Date.now(), // Update timestamp
      }

    } catch (e) {
      console.error('Failed to generate navigation plan', e)
      error.value = e.message || 'ナビゲーションの生成に失敗しました'
    } finally {
      isNavigating.value = false
    }
  }

  if (plan.value?.createdAt && Date.now() - plan.value.createdAt > PLAN_TTL) {
    console.log('Plan expired, resetting...')
    reset()
  }

  const initializeDeviceId = () => {
    deviceId.value = getDeviceUUID()
    console.log('Device ID initialized:', deviceId.value)
  }

  const setItinerary = (itinerary) => {
    console.log('[NavStore] Setting itinerary:', itinerary);
    if (!Array.isArray(itinerary)) {
      console.warn('[NavStore] setItinerary received non-array value:', itinerary);
      return;
    };
    waypointsByIds.value = itinerary;
    if (plan.value) {
      // This is a simplified representation. The full waypoint_info would ideally be fetched or already present.
      plan.value.waypoints_info = itinerary.map(spot_id => ({ spot_id, name: spot_id }));
    } else {
      // If there is no plan, create a minimal one
      plan.value = { waypoints_info: itinerary.map(spot_id => ({ spot_id, name: spot_id })) };
    }
    console.log('[NavStore] Itinerary set. Waypoints by ID:', waypointsByIds.value);
  }

  return {
    // State
    lang,
    origin,
    waypointsByIds,
    plan,
    isRouteLoading,
    isNavigating,
    error,
    deviceId,
    // Getters
    isRouteReady,
    isNavigationReady,
    waypoints,
    alongPois,
    // Actions
    fetchRoute,
    startGuidance,
    reset,
    initializeDeviceId,
    setItinerary,
  }
}, {
  persist: true // LocalStorageに保存
})