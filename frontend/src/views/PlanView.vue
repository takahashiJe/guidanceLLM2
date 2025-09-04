<!-- src/views/PlanView.vue -->
<template>
  <div class="page">
    <header class="bar">
      <h1>プラン作成</h1>
      <router-link to="/nav" class="link">ナビへ</router-link>
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
        <label>スポット（順番可）</label>
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
              <span>{{ nameById(id) }}</span>
              <span class="ops">
                <button @click="move(i, -1)" :disabled="i===0">↑</button>
                <button @click="move(i, +1)" :disabled="i===selectedIds.length-1">↓</button>
                <button class="del" @click="remove(i)">×</button>
              </span>
            </li>
          </ul>
        </div>
      </div>

      <div class="row">
        <button class="primary" :disabled="submitting || selectedIds.length===0" @click="submitPlan">
          この条件でナビ開始
        </button>
        <span v-if="submitting" class="hint">送信中…</span>
      </div>
    </section>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useNavStore } from '@/stores/nav';
import { createPlan, pollPlan } from '@/lib/api';

export default {
  name: 'PlanView',
  setup() {
    const router = useRouter();
    const nav = useNavStore();

    const lang = ref(nav.lang || 'ja');
    const pois = ref([]);            // public/pois.json を読み込む
    const selectedIds = ref([]);     // spot_id の配列
    const submitting = ref(false);

    // ---- POI 読み込み（public/pois.json）----
    async function loadPois() {
      try {
        const res = await fetch('/pois.json', { cache: 'no-cache' });
        const list = await res.json();
        // list: [{ spot_id, official_name:{ja,en,zh}, ... }]
        pois.value = list;
      } catch (e) {
        console.error('[plan] failed to load pois.json', e);
        pois.value = [];
      }
    }

    // 表示名（言語に応じて）
    function displayName(p) {
      const o = (p.official_name || {});
      return (o[lang.value] || o.ja || p.spot_id);
    }
    function nameById(id) {
      const p = pois.value.find(x => x.spot_id === id);
      return p ? displayName(p) : id;
    }

    // 選択＆並べ替え
    function toggleSpot(id) {
      const i = selectedIds.value.indexOf(id);
      if (i >= 0) selectedIds.value.splice(i, 1);
      else selectedIds.value.push(id);
    }
    function move(i, d) {
      const j = i + d;
      if (j < 0 || j >= selectedIds.value.length) return;
      const arr = selectedIds.value;
      [arr[i], arr[j]] = [arr[j], arr[i]];
      selectedIds.value = [...arr];
    }
    function remove(i) {
      selectedIds.value.splice(i, 1);
      selectedIds.value = [...selectedIds.value];
    }

    // 現在地を一度だけ取得（送信直前に使う）
    function getCurrentPositionOnce() {
      return new Promise(resolve => {
        if (!navigator.geolocation) return resolve(null);
        navigator.geolocation.getCurrentPosition(
          pos => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
          _err => resolve(null),
          { enableHighAccuracy: true, timeout: 3000, maximumAge: 5000 }
        );
      });
    }

    // 送信
    async function submitPlan() {
      try {
        submitting.value = true;

        // 直前に origin を最新化
        const fresh = await getCurrentPositionOnce();
        if (fresh) {
          nav.setOrigin(fresh); // ← ストアの origin を更新
        }

        // ストア更新
        nav.setLang(lang.value);
        nav.setWaypoints(selectedIds.value);

        // ペイロード作成
        const payload = {
          language: nav.lang,
          origin: { lat: nav.origin.lat, lon: nav.origin.lon },
          return_to_origin: true,
          waypoints: nav.waypoints.map(id => ({ spot_id: id })),
        };
        console.debug('[plan] payload', payload);

        // 作成→ポーリング
        const { task_id } = await createPlan(payload);
        const plan = await pollPlan(task_id, (tick) =>
          console.debug('[plan] tick', tick)
        );

        // ストアに格納して /nav へ
        nav.setPlan(plan);
        router.push('/nav');
      } catch (e) {
        console.error('[plan] submit error', e);
        alert('プラン作成に失敗しました。通信状態をご確認ください。');
      } finally {
        submitting.value = false;
      }
    }

    onMounted(loadPois);

    return {
      lang, pois, selectedIds, submitting,
      displayName, nameById,
      toggleSpot, move, remove,
      submitPlan,
    };
  }
};
</script>

<style scoped>
.page { max-width: 720px; margin: 0 auto; padding: 8px 12px 24px; }
.bar { display:flex; align-items:center; justify-content:space-between; }
.link { color:#2563eb; text-decoration:none; }
.form { margin-top:8px; }
.row { margin: 12px 0; }
select { padding:8px; font-size:16px; }
.chips { display:flex; flex-wrap:wrap; gap:8px; }
.chip { padding:6px 10px; border:1px solid #ccc; border-radius:16px; background:#fff; }
.chip.on { background:#e8f0fe; border-color:#2563eb; color:#2563eb; }
.reorder ul { list-style: none; padding:0; margin:6px 0 0; }
.reorder li { display:flex; align-items:center; justify-content:space-between; padding:6px 0; border-bottom:1px dashed #eee; }
.ops button { margin-left:6px; }
.del { color:#b91c1c; }
.primary { width:100%; padding:12px; font-size:16px; background:#2563eb; color:#fff; border:none; border-radius:10px; }
.hint { margin-left:8px; color:#777; }
</style>
