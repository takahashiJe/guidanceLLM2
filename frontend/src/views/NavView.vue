<template>
  <div class="page">
    <header class="top">
      <router-link to="/" class="back">← プランへ</router-link>
      <h1>周遊ナビ</h1>
      <div class="pid">#{{ shortId }}</div>
    </header>

    <!-- 順番付きスポットのボタン列 -->
    <div class="chips" v-if="orderedSpots.length">
      <button
        v-for="s in orderedSpots"
        :key="s.spot_id"
        class="chip"
        :class="{ active: s.spot_id === activeId }"
        @click="focus(s.spot_id)"
      >
        <span class="num">{{ s.order }}</span>
        <span class="lbl">{{ s.name }}</span>
      </button>
    </div>

    <NavMap ref="mapRef" :plan="plan" :lang="lang" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useNavStore } from '@/stores/nav'
import { storeToRefs } from 'pinia'
import NavMap from '@/components/NavMap.vue'

const store = useNavStore()
const { plan, lang } = storeToRefs(store)

const mapRef = ref(null)
const activeId = ref(null)

const shortId = computed(() => (plan.value?.pack_id || '').slice(0, 7))

function pickName(s, lang='ja') {
  return (
    s?.official_name?.[lang] ||
    s?.[`name_${lang}`] ||
    s?.name ||
    s?.spot_id ||
    ''
  )
}

const orderedSpots = computed(() => {
  const legs = plan.value?.legs || []
  return legs.map((l, i) => {
    const s = l?.spot || {}
    const sid = String(s.spot_id || s.id || '')
    return {
      spot_id: sid,
      name: pickName(s, lang.value),
      order: i + 1,
      lat: s.lat, lon: s.lon,
    }
  }).filter(s => s.spot_id)
})

function focus(spotId) {
  activeId.value = String(spotId)
  // defineExpose のメソッドを直接呼べる（<script setup>）
  mapRef.value?.focusSpotById(activeId.value)
}

onMounted(() => {
  if (orderedSpots.value.length) {
    focus(orderedSpots.value[0].spot_id)
  }
})
</script>

<style scoped>
.page { padding: 12px; }
.top {
  display: grid; grid-template-columns: 1fr auto 1fr; align-items: center;
  margin-bottom: 8px;
}
.back { justify-self: start; color: #2563eb; font-weight: 600; }
.top h1 { justify-self: center; font-size: 18px; }
.pid { justify-self: end; color: #6b7280; font-size: 12px; }

.chips {
  display: flex; gap: 8px; overflow-x: auto; padding: 8px 0; margin-bottom: 8px;
}
.chip {
  display: inline-flex; align-items: center; gap: 8px;
  border: 1.5px solid #dbe3f4; background: #f8fafc; color: #0f172a;
  padding: 6px 10px; border-radius: 999px;
}
.chip .num {
  display: grid; place-items: center;
  width: 22px; height: 22px; border-radius: 999px; background: #e5edff; color:#1d4ed8; font-weight: 700; font-size: 12px;
}
.chip.active { border-color: #3b82f6; box-shadow: 0 0 0 2px #3b82f633 inset; }
</style>
