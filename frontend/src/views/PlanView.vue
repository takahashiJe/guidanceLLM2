<template>
  <section class="panel">
    <h2>プラン作成</h2>
    <form @submit.prevent="submit">
      <div class="row">
        <label>言語</label>
        <select v-model="language">
          <option value="ja">日本語</option>
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
      </div>

      <div class="row">
        <label>出発地（lat, lon）</label>
        <div class="h">
          <input v-model.number="origin.lat" type="number" step="0.000001" placeholder="lat" />
          <input v-model.number="origin.lon" type="number" step="0.000001" placeholder="lon" />
        </div>
      </div>

      <div class="row">
        <label>スポット（順序）</label>
        <small>例: spot_001,spot_007</small>
        <input v-model="spotLine" placeholder="spot_001,spot_007" />
      </div>

      <button class="btn" :disabled="submitting">{{ submitting ? '送信中…' : 'プラン作成' }}</button>
    </form>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useNavStore } from '@/stores/nav'
import { createPlan, pollPlan } from '@/lib/api'

const router = useRouter()
const nav = useNavStore()

const language = ref('ja')
const origin   = ref({ lat: 39.2201, lon: 139.9006 })
const spotLine = ref('spot_001,spot_007')
const submitting = ref(false)

async function submit () {
  submitting.value = true
  try {
    const waypoints = spotLine.value.split(',').map(s => ({ spot_id: s.trim() })).filter(w => w.spot_id)
    const req = {
      language: language.value,
      origin: origin.value,
      return_to_origin: true,
      waypoints
    }
    const { task_id } = await createPlan(req)

    // ポーリング → 200 になったら store に格納して /nav へ
    const result = await pollPlan(task_id, (tick) => {
      // 進捗が必要ならここで表示可能
    })
    nav.setPlan(result) // store に保存
    router.replace('/nav')
  } catch (e) {
    console.error('[plan] submit error', e)
    alert('プラン作成に失敗しました')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.panel { display: grid; gap: 14px; }
.row { display: grid; gap: 6px; }
.row .h { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
input, select { padding: 10px; border: 1px solid #ddd; border-radius: 8px; }
.btn { padding: 12px; border: 1px solid #ddd; border-radius: 10px; background:#0ea5e9; color:#fff; }
</style>
