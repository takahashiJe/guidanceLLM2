<template>
  <div class="plan-form">
    <div class="toolbar">
      <label>言語</label>
      <select v-model="langLocal">
        <option value="ja">日本語</option>
        <option value="en">English</option>
        <option value="zh">中文</option>
      </select>
    </div>

    <div class="toolbar">
      <input v-model="q" placeholder="スポット検索（名前で絞り込み）" />
    </div>

    <div class="columns">
      <!-- 候補リスト -->
      <div class="col">
        <h3>スポット一覧（{{ filtered.length }}）</h3>
        <ul class="list">
          <li v-for="poi in filtered" :key="poi.spot_id">
            <button class="add" @click="add(poi.spot_id)" :disabled="selectedIds.includes(poi.spot_id)">＋</button>
            <span class="name">{{ displayName(poi) }}</span>
          </li>
        </ul>
      </div>

      <!-- 選択順序 -->
      <div class="col">
        <h3>巡回順（{{ selectedIds.length }}）</h3>
        <ol class="list selected">
          <li v-for="(id, idx) in selectedIds" :key="id">
            <span class="order">{{ idx + 1 }}</span>
            <span class="name">{{ nameById(id) }}</span>
            <span class="actions">
              <button @click="move(idx, -1)" :disabled="idx === 0">↑</button>
              <button @click="move(idx, 1)" :disabled="idx === selectedIds.length - 1">↓</button>
              <button @click="remove(idx)">✕</button>
            </span>
          </li>
        </ol>

        <div class="origin">
          <label>出発地（緯度・経度）</label>
          <div class="row">
            <input type="number" step="0.000001" v-model.number="origin.lat" placeholder="lat">
            <input type="number" step="0.000001" v-model.number="origin.lon" placeholder="lon">
          </div>
        </div>

        <button class="primary" :disabled="!selectedIds.length" @click="start">
          この順でナビ開始
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useNavStore } from '@/stores/nav'

const store = useNavStore()

// ---- ローカル状態（送信時にstoreへ反映） ----
const langLocal = ref(store.lang || 'ja')
const origin = ref({
  lat: store.origin?.lat ?? 39.2201,
  lon: store.origin?.lon ?? 139.9006,
})
const pois = ref([])
const q = ref('')

// storeのフィールド名が「waypoints」「waypointIds」どちらでも拾えるように
const selectedIds = ref(
  Array.isArray(store.waypointIds) ? [...store.waypointIds]
  : Array.isArray(store.waypoints) ? [...store.waypoints]
  : []
)

// ---- POI読み込み（/public/pois.json）----
onMounted(async () => {
  try {
    const res = await fetch('/pois.json', { cache: 'no-store' })
    const arr = await res.json()
    pois.value = Array.isArray(arr) ? arr.filter(p => p && p.spot_id) : []
  } catch (e) {
    console.error('[plan] failed to load /pois.json', e)
    pois.value = []
  }
})

// ---- 表示名ユーティリティ ----
function displayName(poi) {
  const n = (poi?.official_name && poi.official_name[langLocal.value]) || poi?.name
  return (n && String(n)) || poi?.spot_id || '(no name)'
}
function nameById(id) {
  const p = pois.value.find(x => x.spot_id === id)
  return p ? displayName(p) : id
}

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  if (!needle) return pois.value
  return pois.value.filter(p => displayName(p).toLowerCase().includes(needle))
})

// ---- 選択操作 ----
function add(id) {
  if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
}
function remove(idx) {
  selectedIds.value.splice(idx, 1)
}
function move(idx, delta) {
  const ni = idx + delta
  if (ni < 0 || ni >= selectedIds.value.length) return
  const arr = selectedIds.value
  const [v] = arr.splice(idx, 1)
  arr.splice(ni, 0, v)
}

// 親へ送信
const emit = defineEmits(['start'])
function start() {
  emit('start', {
    lang: langLocal.value,
    origin: { lat: Number(origin.value.lat), lon: Number(origin.value.lon) },
    waypoints: [...selectedIds.value],
  })
}
</script>

<style scoped>
.plan-form{ padding:16px; }
.toolbar{ margin:8px 0; display:flex; gap:8px; align-items:center; }
.columns{ display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
@media (max-width: 720px){ .columns{ grid-template-columns: 1fr; } }
.list{ list-style:none; padding:0; margin:8px 0; max-height:60vh; overflow:auto; }
.list li{ display:flex; align-items:center; gap:8px; padding:6px 4px; border-bottom:1px solid #eee; }
.list .add{ width:2.2rem; height:2rem; }
.selected li .order{ width:1.6rem; text-align:right; opacity:.6; }
.actions button{ margin-left:4px; }
.origin{ margin-top:8px; }
.origin .row{ display:flex; gap:8px; }
.primary{ margin-top:12px; width:100%; height:44px; font-size:16px; }
</style>
