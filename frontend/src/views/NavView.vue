<!-- src/views/NavView.vue -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back" @click="goPlan">← プランへ</button>
      <div class="title">周遊ナビ</div>
      <div class="pack" v-if="plan">#{{ packShort }}</div>
    </header>

    <!-- 選択した順序付きスポットをチップで表示（クリックで地図をフォーカス） -->
    <div class="chips" v-if="orderedStops.length">
      <button
        v-for="(s, idx) in orderedStops"
        :key="s.spot_id"
        class="chip"
        :class="{ active: s.spot_id === activeId }"
        @click="focusStop(s.spot_id)"
      >
        <span class="num">{{ idx + 1 }}</span>
        <span class="label">{{ s.name }}</span>
      </button>
    </div>

    <NavMap
      ref="mapRef"
      :plan="plan"
      :stops="orderedStops"
      :lang="lang"
    />
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import NavMap from '@/components/NavMap.vue';
import { useNavStore } from '@/stores/nav';
import { fetchPois } from '@/lib/poi';

const router = useRouter();
const nav = useNavStore();

const plan = computed(() => nav.plan);
const lang = computed(() => nav.lang);

// pois.json を読み込んで index を作る（spot_id -> {name, lat, lon}）
const poiIndex = ref({});
async function ensurePois() {
  const list = await fetchPois();
  const idx = {};
  for (const p of list) idx[p.spot_id] = p;
  poiIndex.value = idx;
}
onMounted(ensurePois);

// store に保持されている選択順を唯一の正とし、表示名は pois.json から引く
const orderedStops = computed(() => {
  const ids = nav.waypoints || [];
  return ids
    .map((id) => {
      const p = poiIndex.value[id];
      // name は言語別 official_name が無いケースも考えて fetchPois 側で正規化済み
      return p ? { spot_id: id, name: p.name, lat: p.lat, lon: p.lon } : { spot_id: id, name: id };
    })
    .filter(Boolean);
});

const packShort = computed(() => (plan.value?.pack_id || '').slice(0, 7));
const mapRef = ref(null);
const activeId = ref(null);

function focusStop(id) {
  activeId.value = id;
  mapRef.value?.focusSpot?.(id);
}

function goPlan() {
  router.push('/plan');
}
</script>

<style scoped>
.page { display:flex; flex-direction:column; height:100vh; }
.topbar {
  display:flex; align-items:center; justify-content:space-between;
  padding:12px 16px; border-bottom:1px solid #e5e7eb; background:#fff;
}
.back { font-size:16px; padding:6px 10px; border:1px solid #d1d5db; border-radius:8px; background:#fff; }
.title { font-weight:600; }
.pack { color:#6b7280; font-family:monospace; }

.chips {
  display:flex; gap:8px; padding:10px 12px; overflow-x:auto; background:#fff;
  border-bottom:1px solid #e5e7eb;
}
.chip {
  display:flex; align-items:center; gap:8px;
  border:1.5px solid #c7d2fe; background:#eef2ff; color:#1e3a8a;
  padding:6px 10px; border-radius:999px; white-space:nowrap;
}
.chip .num {
  width:22px; height:22px; display:inline-grid; place-items:center;
  border-radius:999px; background:#2563eb; color:#fff; font-size:12px;
}
.chip.active { border-color:#2563eb; box-shadow:0 0 0 2px rgba(37,99,235,0.15) inset; }
</style>
