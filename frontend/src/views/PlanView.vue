<script setup>
import { ref, onMounted, computed } from 'vue'
import { useNavStore } from '@/stores/nav'
import { usePosition } from '@/lib/usePosition'

const nav = useNavStore()
const { position, requestPosition } = usePosition()

// 言語の選択状態は、ストアの lang と双方向にバインディングする
const lang = computed({
  get: () => nav.lang,
  set: (val) => nav.setLang(val) // ストアにセッターがあることを想定 (なければ nav.lang = val)
})

const pois = ref([])
const selectedIds = ref([])

// --- POIデータ読み込み ---
onMounted(async () => {
  try {
    const res = await fetch('/pois.json', { cache: 'no-cache' })
    pois.value = await res.json()
    requestPosition()
  } catch (e) {
    console.error('[plan] failed to load pois.json', e)
  }
})

// --- UI用ヘルパー関数 ---
function displayName(p) {
  const o = p.official_name || {}
  return o[lang.value] || o.ja || p.spot_id
}

function nameById(id) {
  const p = pois.value.find((x) => x.spot_id === id)
  return p ? displayName(p) : id
}

// --- 選択・並べ替えロジック ---
function toggleSpot(id) {
  const i = selectedIds.value.indexOf(id)
  if (i >= 0) {
    selectedIds.value.splice(i, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function move(i, d) {
  const j = i + d
  if (j < 0 || j >= selectedIds.value.length) return
  const temp = selectedIds.value[i]
  selectedIds.value[i] = selectedIds.value[j]
  selectedIds.value[j] = temp
}

function remove(i) {
  selectedIds.value.splice(i, 1)
}


// --- ★★★ ここからが修正箇所 ★★★ ---

// ストアのトップレベルのプロパティを直接参照するように修正
const isRouteLoading = computed(() => nav.isRouteLoading)
const hasError = computed(() => nav.error)
const hasNoPosition = computed(() => !position.value.coords)

/**
 * ルート計画の作成をストアのアクションに依頼する
 */
async function submitPlan() {
  if (hasNoPosition.value) {
    alert('現在地が取得できていません。ブラウザのGPS利用を許可してください。')
    return
  }

  const planOptions = {
    language: lang.value,
    origin: {
      lat: position.value.coords.latitude,
      lon: position.value.coords.longitude
    },
    waypoints: selectedIds.value.map((id) => ({ spot_id: id }))
  }

  // ストアの新しいアクションを呼び出す
  await nav.fetchRoute(planOptions)
  // ページ遷移はストアのアクション内で行われる
}
</script>

<template>
  <div class="page">
    <header class="bar">
      <h1>ナビ計画</h1>
    </header>

    <section class="form">
      <div class="row">
        <label for="lang">表示言語</label>
        <select id="lang" v-model="lang">
          <option value="ja">日本語</option>
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
      </div>

      <div class="row">
        <label>スポット選択（複数可・順番に周遊）</label>
        <div class="chips">
          <button
            v-for="p in pois"
            :key="p.spot_id"
            @click="toggleSpot(p.spot_id)"
            :class="{ chip: true, on: selectedIds.includes(p.spot_id) }"
          >
            {{ displayName(p) }}
          </button>
        </div>
      </div>

      <div class="row" v-if="selectedIds.length > 0">
        <label>訪問順</label>
        <div class="reorder">
          <ul>
            <li v-for="(id, i) in selectedIds" :key="id">
              <span class="name">{{ i + 1 }}. {{ nameById(id) }}</span>
              <span class="ctrl">
                <button class="up" :disabled="i === 0" @click="move(i, -1)">↑</button>
                <button class="down" :disabled="i === selectedIds.length - 1" @click="move(i, 1)">
                  ↓
                </button>
                <button class="del" @click="remove(i)">×</button>
              </span>
            </li>
          </ul>
        </div>
      </div>

      <div v-if="hasError" class="error-box">
        <p>エラーが発生しました:</p>
        <pre>{{ nav.error }}</pre>
      </div>
      <div v-if="hasNoPosition" class="error-box">
        <p>現在地を取得中です...</p>
      </div>

      <div class="row">
        <button
          class="primary"
          :disabled="isRouteLoading || selectedIds.length === 0 || hasNoPosition"
          @click="submitPlan"
        >
          {{ isRouteLoading ? 'ルート作成中...' : 'ルートを作成して地図で確認' }}
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* styleブロックは変更なし */
.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 8px 12px 24px;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.form {
  margin-top: 8px;
}
.row {
  margin: 16px 0;
}
label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
}
select {
  padding: 8px;
  font-size: 16px;
  width: 100%;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  padding: 6px 12px;
  border: 1px solid #ccc;
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
}
.chip.on {
  background: #e8f0fe;
  border-color: #2563eb;
  color: #2563eb;
  font-weight: bold;
}
.reorder {
  margin-top: 16px;
}
.reorder ul {
  list-style: none;
  padding: 0;
  margin: 0;
  border: 1px solid #ccc;
  border-radius: 8px;
  overflow: hidden;
}
.reorder li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
}
.reorder li:last-child {
  border-bottom: none;
}
.reorder .name {
  font-size: 16px;
}
.reorder .ctrl {
  display: flex;
  gap: 4px;
}
.reorder .ctrl button {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  border: 1px solid #ccc;
  background: #f8f8f8;
  cursor: pointer;
}
.reorder .ctrl button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.reorder .ctrl button.del {
  border-color: #e11d48;
  color: #e11d48;
}

button.primary {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  background: #1d4ed8;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
button.primary:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.error-box {
  border: 1px solid #f87171;
  background-color: #fef2f2;
  color: #b91c1c;
  padding: 10px;
  border-radius: 6px;
  margin-top: 16px;
}
</style>