<!-- src/views/PlanView.vue -->
<template>
  <div class="p-3">
    <header class="flex items-center gap-2 mb-3">
      <h1 class="text-xl font-semibold">周遊プラン</h1>
      <router-link class="ml-auto px-3 py-2 rounded bg-gray-200" to="/nav">ナビへ</router-link>
    </header>

    <!-- 既存の PlanForm をそのまま活用 -->
    <PlanForm @submit="onSubmit" :busy="busy" />

    <div v-if="store.polling" class="mt-4 text-sm text-gray-600">
      ルート生成中…（バックエンドへ問い合わせ中）
    </div>
    <ul v-if="store.pollLog.length" class="mt-2 text-xs text-gray-500 space-y-1">
      <li v-for="(l,i) in store.pollLog" :key="i">{{ l }}</li>
    </ul>
  </div>
</template>

<script>
import { useRouter } from 'vue-router'
import { useNavStore } from '@/stores/nav'
import PlanForm from '@/components/PlanForm.vue'

export default {
  name: 'PlanView',
  components: { PlanForm },
  setup() {
    const router = useRouter()
    const store  = useNavStore()
    const busy   = ref(false)

    async function onSubmit({ origin, language, waypoints }) {
      busy.value = true
      try {
        store.setLang(language)
        store.setWaypoints(waypoints)
        await store.submitPlan(origin)  // 送信 & ポーリング開始
        router.push('/nav')             // すぐナビ画面へ遷移（結果は自動反映）
      } catch (e) {
        console.error(e)
        alert('プラン作成に失敗しました')
      } finally {
        busy.value = false
      }
    }

    return { store, busy, onSubmit }
  }
}
</script>

<style scoped>
</style>
