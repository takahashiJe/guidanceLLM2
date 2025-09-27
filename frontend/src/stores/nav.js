import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useRouter } from 'vue-router'
import * as api from '@/lib/api'

// 30分
const PLAN_TTL = 30 * 60 * 1000

export const useNavStore = defineStore('nav', () => {
  const router = useRouter()

  // --- State ---
  // ★★★ 修正箇所 ★★★
  // 元の構造を維持しつつ、新しいUI状態フラグを追加
  
  // 1. 計画作成時のオプション（リファクタリング前の構造を維持）
  const lang = ref('ja')
  const origin = ref(null)
  const waypointsByIds = ref([])
  
  // 2. APIから取得した計画データ
  const plan = ref(null) // ルート情報とガイダンス情報をここにマージしていく
  
  // 3. UIの状態を管理する新しいフラグ
  const isRouteLoading = ref(false)   // ルート計算中
  const isNavigating = ref(false)     // ガイダンス生成タスク実行中
  const error = ref(null)             // エラーメッセージ
  const taskId = ref(null)            // CeleryタスクID

  // 4. 内部管理用
  let pollTimer = null

  // --- Getters ---
  // ★★★ 修正箇所 ★★★
  // isRouteReady と isNavigationReady を getter として定義

  const isRouteReady = computed(() => !!plan.value?.route)
  const isNavigationReady = computed(() => !!plan.value?.assets && plan.value.assets.length > 0)

  // ゲッターは元の実装のままで正しく動作するため変更なし
  const waypoints = computed(() => plan.value?.waypoints_info || [])
  const alongPois = computed(() => plan.value?.along_pois || [])

  // --- Actions ---

  /**
   * ストアを初期状態にリセットする
   */
  const reset = () => {
    lang.value = 'ja'
    origin.value = null
    waypointsByIds.value = []
    plan.value = null
    isRouteLoading.value = false
    isNavigating.value = false
    error.value = null
    taskId.value = null
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    console.log('NavStore reset')
  }

  /**
   * 【ステップ1】ルート計画を作成し、地図表示の準備をする
   * @param {object} planOptions
   */
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

  /**
   * 【ステップ2】ガイダンスの生成を開始し、結果をポーリングする
   */
  const startGuidance = async () => {
    if (!isRouteReady.value || isNavigating.value) return
    
    isNavigating.value = true
    error.value = null
    try {
      // 現在ストアに保持しているルート情報をバックエンドに渡す
      const navRequestPayload = {
        language: lang.value,
        buffer: { car: 300, foot: 10 },
        route: plan.value.route,
        polyline: plan.value.polyline,
        segments: plan.value.segments,
        legs: plan.value.legs,
        waypoints_info: plan.value.waypoints_info,
      }

      const task = await api.startNavigationTask(navRequestPayload)
      taskId.value = task.task_id
      console.log('Navigation task started:', taskId.value)
      pollPlanResult(taskId.value)

    } catch (e) {
      console.error('Failed to start navigation task', e)
      error.value = e.message || 'ナビゲーションの開始に失敗しました'
      isNavigating.value = false
    }
  }

  /**
   * タスクの結果をポーリングで取得する
   * @param {string} currentTaskId
   */
  const pollPlanResult = async (currentTaskId) => {
    if (pollTimer) clearTimeout(pollTimer)

    try {
      const res = await api.getPlanResult(currentTaskId)
      
      if (res.ready === false) { // 202 Accepted
        console.log(`Task ${currentTaskId} is still running... polling again in 5s`)
        pollTimer = setTimeout(() => pollPlanResult(currentTaskId), 5000)
      } else { // 200 OK
        console.log('Task finished, plan received:', res)
        
        // 受信したガイダンス情報を既存のplanオブジェクトにマージ
        plan.value = {
          ...plan.value, // 既存のルート情報を維持
          pack_id: res.pack_id,
          along_pois: res.along_pois,
          assets: res.assets,
          manifest_url: res.manifest_url,
          createdAt: Date.now()
        }
        isNavigating.value = false
      }
    } catch (e) {
      console.error('Failed to poll plan result', e)
      error.value = e.message
      isNavigating.value = false
    }
  }

  // TTLチェックは pinia-plugin-persistedstate があれば不要になることが多いが、念のため残す
  if (plan.value?.createdAt && Date.now() - plan.value.createdAt > PLAN_TTL) {
    console.log('Plan expired, resetting...')
    reset()
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
    // Getters
    isRouteReady,
    isNavigationReady,
    waypoints,
    alongPois,
    // Actions
    fetchRoute,
    startGuidance,
    reset,
  }
}, {
  persist: true // LocalStorageに保存
})
