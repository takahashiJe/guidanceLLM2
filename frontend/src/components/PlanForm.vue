<!-- src/components/PlanForm.vue -->
<template>
  <form @submit.prevent="submit">
    <div class="field">
      <label>言語</label>
      <select v-model="language">
        <option value="ja">日本語</option>
        <option value="en">English</option>
        <option value="zh">中文（普通话）</option>
      </select>
    </div>

    <div class="field">
      <label>出発地（緯度）</label>
      <input type="number" step="0.000001" v-model.number="origin.lat" />
    </div>
    <div class="field">
      <label>出発地（経度）</label>
      <input type="number" step="0.000001" v-model.number="origin.lon" />
    </div>

    <div class="field">
      <label>スポット（順番どおり選択 / 仮UI）</label>
      <div class="spots">
        <label v-for="s in spots" :key="s.id" class="chip">
          <input type="checkbox" :value="s.id" v-model="selected" />
          {{ s.label }}
        </label>
      </div>
      <small>上から順に巡ります（A→B→C）。</small>
    </div>

    <button class="primary" :disabled="submitting || selected.length === 0">
      {{ submitting ? '送信中…' : 'ルート作成' }}
    </button>
  </form>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const props = defineProps({
  submitting: { type: Boolean, default: false }
});

const language = ref('ja');
const origin = ref({ lat: 39.2201, lon: 139.9006 });

const spots = [
  { id: 'spot_001', label: 'あがりこ大王' },
  { id: 'spot_007', label: '法体の滝' },
  { id: 'spot_011', label: '道の駅象潟' },
  { id: 'spot_014', label: '象潟郷土資料館' },
  { id: 'spot_021', label: '蚶満寺' },
];
const selected = ref(['spot_001', 'spot_007']); // デフォルト例

function geolocate() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition((pos) => {
    origin.value.lat = Number(pos.coords.latitude.toFixed(6));
    origin.value.lon = Number(pos.coords.longitude.toFixed(6));
  });
}

onMounted(() => geolocate());

const emit = defineEmits(['submit']);
function submit() {
  const waypoints = selected.value.slice(); // 並び順をそのまま送る
  emit('submit', {
    language: language.value,
    origin: { lat: Number(origin.value.lat), lon: Number(origin.value.lon) },
    waypoints, // [ "spot_001", ... ]
  });
}
</script>

<style scoped>
.field { margin-bottom: 12px; display: grid; gap: 6px; }
.spots { display:flex; flex-wrap:wrap; gap:8px; }
.chip { border:1px solid #ddd; border-radius:14px; padding:6px 10px; }
.primary {
  width:100%; padding:12px; border:none; border-radius:8px;
  background:#0066ff; color:#fff; font-size:16px;
}
</style>
