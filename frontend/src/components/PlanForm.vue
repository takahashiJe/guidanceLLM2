<!-- src/components/PlanForm.vue -->
<template>
  <form class="form" @submit.prevent="onSubmit">
    <div class="row">
      <label>言語</label>
      <select v-model="lang">
        <option value="ja">日本語</option>
        <option value="en">English</option>
        <option value="zh">中文</option>
      </select>
    </div>

    <div class="row">
      <label>スポットID（カンマ区切り）</label>
      <input v-model="waypointsCsv" placeholder="spot_001,spot_007" />
    </div>

    <div class="row">
      <label>出発位置</label>
      <div class="row-inline">
        <input v-model.number="origin.lat" type="number" step="0.000001" placeholder="lat" />
        <input v-model.number="origin.lon" type="number" step="0.000001" placeholder="lon" />
        <button type="button" @click="useCurrent">現在地</button>
      </div>
    </div>

    <button class="primary" type="submit">プラン作成</button>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { useNavStore } from '@/stores/nav'

const nav = useNavStore()
const lang = ref(nav.lang)
const waypointsCsv = ref('')
const origin = ref({ lat: 39.2201, lon: 139.9006 })

async function useCurrent() {
  try {
    const pos = await new Promise((res, rej) =>
      navigator.geolocation.getCurrentPosition(res, rej, { enableHighAccuracy: true })
    )
    origin.value = { lat: pos.coords.latitude, lon: pos.coords.longitude }
  } catch (_) {}
}

async function onSubmit() {
  nav.setLang(lang.value)
  const ids = waypointsCsv.value.split(',').map(s => s.trim()).filter(Boolean)
  nav.setWaypoints(ids)
  await nav.submitPlan(origin.value)
  // ポーリングは親で実行
}
</script>

<style scoped>
.form { padding: 12px; display: grid; gap: 12px; }
.row { display: grid; gap: 6px; }
.row-inline { display: flex; gap: 6px; }
.primary { padding: 10px 12px; font-size: 16px; }
input, select, button { font-size: 16px; }
</style>
