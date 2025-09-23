<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useNavStore } from '@/stores/nav';
import { createPlan, pollPlan } from '@/lib/api';

const router = useRouter();
const nav = useNavStore();

const lang = ref(nav.lang);
const pois = ref([]);
const selectedIds = ref([]);
const submitting = ref(false);

// --- POIデータ読み込み ---
onMounted(async () => {
  try {
    const res = await fetch('/pois.json', { cache: 'no-cache' });
    pois.value = await res.json();
  } catch (e) {
    console.error('[plan] failed to load pois.json', e);
  }
});

// --- UI用ヘルパー関数 ---
function displayName(p) {
  const o = (p.official_name || {});
  return (o[lang.value] || o.ja || p.spot_id);
}

function nameById(id) {
  const p = pois.value.find(x => x.spot_id === id);
  return p ? displayName(p) : id;
}

// --- 選択・並べ替えロジック ---
function toggleSpot(id) {
  const i = selectedIds.value.indexOf(id);
  if (i >= 0) {
    selectedIds.value.splice(i, 1);
  } else {
    selectedIds.value.push(id);
  }
}

function move(i, d) {
  const j = i + d;
  if (j < 0 || j >= selectedIds.value.length) return;
  const arr = selectedIds.value;
  [arr[i], arr[j]] = [arr[j], arr[i]];
}

function remove(i) {
  selectedIds.value.splice(i, 1);
}

// --- 現在地取得 ---
function getCurrentPositionOnce() {
  return new Promise(resolve => {
    if (!navigator.geolocation) {
      return resolve(null);
    }
    navigator.geolocation.getCurrentPosition(
      pos => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 3000, maximumAge: 5000 }
    );
  });
}

// --- 送信処理 ---
async function submitPlan() {
  if (submitting.value || selectedIds.value.length === 0) return;

  try {
    submitting.value = true;

    const freshOrigin = await getCurrentPositionOnce();
    if (freshOrigin) {
      nav.setOrigin(freshOrigin);
    }

    nav.setLang(lang.value);
    nav.setWaypointsByIds(selectedIds.value);

    const payload = {
      language: nav.lang,
      origin: { lat: nav.origin.lat, lon: nav.origin.lon },
      return_to_origin: true,
      waypoints: nav.waypointsByIds.map(id => ({ spot_id: id })),
    };
    
    console.debug('[plan] payload', payload);

    const { task_id } = await createPlan(payload);
    const planResult = await pollPlan(task_id, (tick) =>
      console.debug('[plan] tick', tick)
    );

    nav.setPlan(planResult);
    router.push('/nav');

  } catch (e) {
    console.error('[plan] submit error', e);
    alert('プランの作成に失敗しました。通信状態を確認するか、時間をおいて再度お試しください。');
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="page">
    <header class="bar">
      <h1>プラン作成</h1>
    </header>

    <section class="form">
      <div class="row">
        <label>言語</label>
        <select v-model="lang">
          <option value="ja">日本語</option>
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
      </div>

      <div class="row">
        <label>スポット（訪問したい順に選択・並べ替え）</label>
        <div class="chips">
          <button
            v-for="p in pois"
            :key="p.spot_id"
            :class="['chip', selectedIds.includes(p.spot_id) ? 'on' : '']"
            @click="toggleSpot(p.spot_id)"
          >
            {{ displayName(p) }}
          </button>
        </div>

        <div v-if="selectedIds.length" class="reorder">
          <h4>訪問順</h4>
          <ul>
            <li v-for="(id, i) in selectedIds" :key="id">
              <span>{{ i + 1 }}. {{ nameById(id) }}</span>
              <span class="ops">
                <button @click="move(i, -1)" :disabled="i === 0">↑</button>
                <button @click="move(i, 1)" :disabled="i === selectedIds.length - 1">↓</button>
                <button class="del" @click="remove(i)">×</button>
              </span>
            </li>
          </ul>
        </div>
      </div>

      <div class="row">
        <button class="primary" :disabled="submitting || selectedIds.length === 0" @click="submitPlan">
          {{ submitting ? '作成中...' : 'この条件でナビ開始' }}
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page { max-width: 720px; margin: 0 auto; padding: 8px 12px 24px; }
.bar { display:flex; align-items:center; justify-content:space-between; }
.form { margin-top:8px; }
.row { margin: 16px 0; }
label { display: block; margin-bottom: 8px; font-weight: bold; }
select { padding:8px; font-size:16px; width: 100%; }
.chips { display:flex; flex-wrap:wrap; gap:8px; }
.chip { padding:6px 12px; border:1px solid #ccc; border-radius:16px; background:#fff; cursor: pointer; transition: all 0.2s; }
.chip.on { background:#e8f0fe; border-color:#2563eb; color:#2563eb; font-weight: bold; }
.reorder { margin-top: 16px; }
.reorder ul { list-style: none; padding:0; margin:6px 0 0; }
.reorder li { display:flex; align-items:center; justify-content:space-between; padding:8px 4px; border-bottom:1px solid #eee; }
.ops button { margin-left:6px; }
.del { color:#b91c1c; }
.primary { width:100%; padding:12px; font-size:16px; background:#2563eb; color:#fff; border:none; border-radius:10px; cursor: pointer; }
.primary:disabled { background: #ccc; cursor: not-allowed; }
</style>