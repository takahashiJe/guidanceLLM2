<!-- src/views/NavView.vue -->
<template>
  <div class="h-screen flex flex-col">
    <header class="p-3 flex items-center gap-2">
      <button class="px-3 py-2 rounded bg-gray-200" @click="goPlan">プランへ</button>
      <div class="ml-2 text-sm text-gray-600">
        半径 {{ store.proximityMeters }} m（近接監視: 常時ON）
      </div>
      <div class="ml-auto text-xs text-gray-500" v-if="store.packId">
        pack: {{ store.packId }}
      </div>
    </header>

    <div class="flex-1 min-h-0">
      <NavMap :plan="store.plan" />
    </div>
  </div>
</template>

<script>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNavStore } from '@/stores/nav'
import NavMap from '@/components/NavMap.vue'

export default {
  name: 'NavView',
  components: { NavMap },
  setup() {
    const router = useRouter()
    const store  = useNavStore()

    function goPlan() {
      router.push('/plan')
    }

    onMounted(() => {
      // ナビ画面に入ったら常に近接監視ON
      store.startProximityWatcher()
    })
    onUnmounted(() => {
      store.stopProximityWatcher()
    })

    return { store, goPlan }
  }
}
</script>

<style scoped>
</style>
