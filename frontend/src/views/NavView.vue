<template>
  <main class="page">
    <section class="panel">
      <h1>周遊プラン</h1>

      <form @submit.prevent="onSubmit" class="form">
        <label>言語
          <select v-model="form.language" required>
            <option value="ja">日本語</option>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </label>

        <label>出発位置 (lat, lon)
          <div class="grid2">
            <input v-model.number="form.origin.lat" type="number" step="0.000001" required />
            <input v-model.number="form.origin.lon" type="number" step="0.000001" required />
          </div>
        </label>

        <label class="row">
          <input type="checkbox" v-model="form.return_to_origin" />
          出発位置に戻る
        </label>

        <label>スポット順（spot_idをカンマ区切り）
          <input v-model="spotList" placeholder="spot_001,spot_007" />
        </label>

        <button :disabled="submitting">
          {{ submitting ? '作成中…' : 'プラン作成' }}
        </button>
      </form>

      <p v-if="taskId && !plan">タスクID: {{ taskId }} / 生成中…</p>
      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <section class="map">
      <NavMap v-if="plan" :plan="plan" />
      <div v-else class="placeholder">プランを作成すると地図が表示されます</div>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import { createPlan, fetchPlanResult } from '../lib/api'
import NavMap from '../components/NavMap.vue'

const submitting = ref(false)
const taskId = ref('')
const plan = ref(null)
const error = ref('')

const form = ref({
  language: 'ja',
  origin: { lat: 39.2201, lon: 139.9006 },
  return_to_origin: true,
})
const spotList = ref('spot_001,spot_007')

async function onSubmit() {
  error.value = ''
  plan.value = null
  submitting.value = true
  try {
    const waypoints = spotList.value
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
      .map(spot_id => ({ spot_id }))

    const accepted = await createPlan({
      language: form.value.language,
      origin: form.value.origin,
      return_to_origin: form.value.return_to_origin,
      waypoints,
    })
    taskId.value = accepted.task_id

    // ポーリング
    let tries = 0
    while (tries < 120) { // 最大約2分
      const { status, data } = await fetchPlanResult(taskId.value)
      if (status === 200) {
        plan.value = data
        break
      } else if (status === 500) {
        throw new Error('サーバエラー（nav.plan 失敗）')
      }
      await new Promise(r => setTimeout(r, 1000))
      tries++
    }
    if (!plan.value) throw new Error('タイムアウト')
  } catch (e) {
    error.value = String(e?.message || e)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.page {
  display: grid;
  grid-template-rows: auto 1fr;
  height: 100vh;
}
.panel {
  padding: 12px;
  background: #fff;
  border-bottom: 1px solid #eee;
}
.form {
  display: grid;
  gap: 8px;
}
.grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.row {
  display: flex;
  gap: 8px;
  align-items: center;
}
button {
  padding: 10px 12px;
  border: none;
  border-radius: 10px;
  background: #2a7cf7;
  color: #fff;
  font-size: 16px;
}
.map {
  min-height: 0;
}
.placeholder {
  height: 100%;
  display: grid;
  place-items: center;
  color: #888;
}
.error {
  color: #d00;
}
</style>
