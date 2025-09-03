<template>
  <main class="h-[100dvh] flex flex-col">
    <!-- 上部バー：プランへ戻る -->
    <header class="p-3 border-b flex items-center gap-2 bg-white/90">
      <button @click="toPlan" class="px-3 py-1 rounded border text-sm">
        ← プランへ
      </button>
      <div class="font-bold text-base flex-1 text-center">ナビ</div>
      <div class="text-[11px] text-gray-500" v-if="packId">
        pack: {{ shortPack }}
      </div>
    </header>

    <!-- 地図 -->
    <section class="flex-1">
      <NavMap />
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useNavStore } from '@/stores/nav'
import NavMap from '@/components/NavMap.vue'

const store = useNavStore()
const router = useRouter()

const packId = computed(() => store.packId)
const shortPack = computed(() => (packId.value ? packId.value.slice(0, 8) : ''))

function toPlan() {
  router.push({ name: 'plan' })
}

// 「常にON」— 画面に入ったら開始、離脱したら停止
onMounted(() => {
  store.startProximityWatcher()
})
onBeforeUnmount(() => {
  store.stopProximityWatcher()
})
</script>
