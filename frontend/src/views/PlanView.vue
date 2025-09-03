<template>
  <main class="p-3 space-y-4">
    <h1 class="text-xl font-bold">ナビプラン作成</h1>

    <section class="space-y-3">
      <div class="flex items-center gap-2">
        <label class="w-28">言語</label>
        <select v-model="lang" class="border rounded px-2 py-1 w-full">
          <option value="ja">日本語</option>
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
      </div>

      <div>
        <label class="block mb-1">スポットID（順番どおり / カンマ区切り）</label>
        <input v-model="waypointText" placeholder="spot_001,spot_007" class="border rounded px-2 py-1 w-full" />
      </div>

      <div class="flex gap-2">
        <button @click="onSubmit" class="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50" :disabled="submitting">
          {{ submitting ? '送信中…' : 'プラン作成' }}
        </button>
        <button @click="toMap" class="bg-gray-200 px-4 py-2 rounded">地図へ</button>
      </div>
    </section>

    <section v-if="taskId || polling" class="space-y-2">
      <div class="font-semibold">ポーリング</div>
      <div class="text-sm text-gray-600">task_id: {{ taskId || '-' }}</div>
      <ul class="text-sm bg-gray-50 border rounded p-2 max-h-40 overflow-auto">
        <li v-for="(l,idx) in pollLog" :key="idx">{{ l }}</li>
      </ul>
    </section>

    <section v-if="packId" class="space-y-2">
      <div class="font-semibold">準備完了</div>
      <div>pack_id: <code>{{ packId }}</code></div>
      <div class="text-sm">自動で地図へ移動します…（うまく行かないときは「地図へ」を押してください）</div>
    </section>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useNavStore } from '@/stores/nav';

const store = useNavStore();
const router = useRouter();

const lang = ref(store.lang);
const waypointText = ref('spot_001,spot_007');

const submitting = ref(false);

const taskId = computed(() => store.taskId);
const pollLog = computed(() => store.pollLog);
const polling = computed(() => store.polling);
const packId = computed(() => store.packId);

// packId が入ったら自動で地図へ
watch(packId, (v) => {
  if (v) router.push({ name: 'nav' });
});

async function onSubmit() {
  submitting.value = true;
  try {
    store.setLang(lang.value);
    const ids = waypointText.value.split(',').map(s => s.trim()).filter(Boolean);
    store.setWaypoints(ids);

    // 位置情報（起点）。取れなくても既定を使用
    let origin = { lat: 39.2201, lon: 139.9006 };
    try {
      const p = await new Promise((res, rej) =>
        navigator.geolocation.getCurrentPosition(res, rej, { enableHighAccuracy: true, timeout: 8000 })
      );
      origin = { lat: p.coords.latitude, lon: p.coords.longitude };
    } catch (_) {}

    await store.submitPlan(origin); // 内部で自動ポーリング → 200 で plan 格納 & プリフェッチ
  } catch (e) {
    alert(e?.message || e);
  } finally {
    submitting.value = false;
  }
}

function toMap() {
  router.push({ name: 'nav' });
}
</script>

<style scoped>
main { max-width: 640px; margin: 0 auto; }
</style>
