<template>
  <div class="nav-view">
    <header class="nav-toolbar">
      <div class="title">
        <span class="label">パックID</span>
        <span class="value" v-if="plan">{{ plan.pack_id }}</span>
        <span class="value" v-else>—</span>
      </div>

      <div class="chips" v-if="spots.length">
        <button
          v-for="(p, idx) in spots"
          :key="p.spot_id || `${p.lat},${p.lon}`"
          class="chip"
          :class="{ active: p.spot_id === activeSpotId }"
          @click="focusSpot(p, idx)"
        >
          <span class="num">{{ idx + 1 }}</span>
          <span class="name">{{ p.name || '無名スポット' }}</span>
        </button>
      </div>
    </header>

    <section class="map-wrap">
      <NavMap
        ref="mapRef"
        :plan="plan"
        :pois="spots"
      />
    </section>

    <section v-if="!plan" class="empty">
      プランがまだありません。PlanForm から作成してください。
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
// ※ プロジェクトのエイリアス設定に合わせてください（Vite の既定なら '@' でOK）
import { useNavStore } from '@/stores/nav'
import NavMap from '@/components/NavMap.vue'

const store = useNavStore()
const mapRef = ref(null)

const plan = computed(() => store.plan || null)
// along_pois の中からスポット系のみ（kind が無い場合はスポットとして扱う）
const spots = computed(() =>
  (plan.value?.along_pois || []).filter(p => !p.kind || p.kind === 'spot')
)

const activeSpotId = ref(null)

function focusSpot(poi, idx) {
  activeSpotId.value = poi.spot_id || null
  // マップへフォーカス要求（存在しないIDでも安全に何もしません）
  mapRef.value?.focusOnSpot(poi.spot_id, {
    // スポットが無名でもUI側の番号と同期
    fallbackTitle: `${idx + 1}. ${poi.name || '無名スポット'}`
  })
}

onMounted(() => {
  // 音声の自動再生トリガ（近接）— 既存ストアの実装を利用
  if (typeof store.startProximityWatcher === 'function') {
    store.startProximityWatcher()
  }
})

onBeforeUnmount(() => {
  if (typeof store.stopProximityWatcher === 'function') {
    store.stopProximityWatcher()
  }
})
</script>

<style scoped>
.nav-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100dvh;
}

.nav-toolbar {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 10;
}

.title {
  display: flex;
  gap: 8px;
  align-items: baseline;
  white-space: nowrap;
}
.title .label {
  font-size: 12px;
  color: #6b7280;
}
.title .value {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  color: #111827;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 6px;
}

.chips {
  display: flex;
  overflow-x: auto;
  gap: 8px;
  padding-bottom: 2px;
  scrollbar-width: thin;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
  font-size: 13px;
  white-space: nowrap;
}
.chip .num {
  display: inline-grid;
  place-items: center;
  width: 20px;
  height: 20px;
  font-weight: 700;
  border-radius: 999px;
  border: 1px solid #d1d5db;
}
.chip.active {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37,99,235,.15) inset;
}
.chip.active .num {
  background: #2563eb;
  color: #fff;
  border-color: transparent;
}
.chip:active { transform: translateY(1px); }

.map-wrap {
  position: relative;
  flex: 1 1 auto;
  min-height: 420px;
}

/* 空表示 */
.empty {
  padding: 16px;
  color: #6b7280;
}
</style>
