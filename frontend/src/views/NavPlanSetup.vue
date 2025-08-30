<template>
  <div class="h-full w-full flex flex-col">
    <header class="p-3 border-b flex items-center justify-between lg:hidden bg-white">
      <h1 class="font-semibold">周遊プラン作成</h1>
      <RouterLink to="/nav/run" class="text-sm text-blue-600" v-if="ready">ナビへ</RouterLink>
    </header>

    <div class="p-4 space-y-4">
      <div class="bg-white rounded-xl shadow-sm p-4 space-y-3">
        <div class="grid grid-cols-3 gap-2">
          <label class="col-span-1 text-sm text-gray-500">言語</label>
          <select v-model="req.language" class="col-span-2 border rounded-lg px-3 py-2">
            <option value="ja">日本語</option>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </div>

        <div class="grid grid-cols-3 gap-2">
          <label class="col-span-1 text-sm text-gray-500">バッファ</label>
          <div class="col-span-2 flex gap-2">
            <input type="number" class="border rounded-lg px-3 py-2 w-24" v-model.number="req.buffers.car" placeholder="car(m)">
            <input type="number" class="border rounded-lg px-3 py-2 w-24" v-model.number="req.buffers.foot" placeholder="foot(m)">
          </div>
        </div>

        <div>
          <label class="text-sm text-gray-500">スポット順序（spot_id）</label>
          <div class="flex gap-2 mt-2">
            <input v-model="spotIdInput" class="border rounded-lg px-3 py-2 flex-1" placeholder="spot_hottai_falls 等">
            <button class="px-3 py-2 rounded-lg bg-gray-900 text-white" @click="addSpot">追加</button>
          </div>
          <ul class="mt-2 flex flex-wrap gap-2">
            <li v-for="(w,i) in req.waypoints" :key="i" class="px-2 py-1 bg-gray-100 rounded-md text-sm flex items-center gap-2">
              <span>{{ w.spot_id || (w.lat + ',' + w.lon) }}</span>
              <button class="text-gray-500" @click="remove(i)">✕</button>
            </li>
          </ul>
        </div>

        <button class="w-full py-3 rounded-xl bg-blue-600 text-white disabled:opacity-50"
                :disabled="req.waypoints.length < 1 || loading"
                @click="plan">
          {{ loading ? '作成中…' : 'プラン作成 & 音声プリフェッチ' }}
        </button>
      </div>

      <div v-if="store.prefetch.inProgress || ready" class="bg-white rounded-xl shadow-sm p-4">
        <div class="flex justify-between text-sm mb-1">
          <span>プリフェッチ</span><span>{{ store.prefetch.done }} / {{ store.prefetch.total }}</span>
        </div>
        <div class="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
          <div class="h-full bg-blue-600" :style="{ width: pct + '%' }"></div>
        </div>
        <p v-if="store.prefetch.error" class="text-red-600 text-sm mt-2">Error: {{ store.prefetch.error }}</p>
        <RouterLink v-if="ready" to="/nav/run" class="mt-3 inline-block text-blue-600 text-sm">ナビを開始 →</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, computed, ref } from "vue";
import { usePlanStore } from "@/stores/planStore";

const store = usePlanStore();
const loading = ref(false);
const spotIdInput = ref("");

const req = reactive({
  language: "ja",
  waypoints: [],
  buffers: { car: 300, foot: 10 },
});

function addSpot() {
  const id = spotIdInput.value.trim();
  if (!id) return;
  req.waypoints.push({ spot_id: id });
  spotIdInput.value = "";
}
function remove(i){ req.waypoints.splice(i,1); }

const pct = computed(() => {
  const t = store.prefetch.total || 1;
  return Math.min(100, Math.round((store.prefetch.done / t) * 100));
});
const ready = computed(() =>
  store.current && store.prefetch.done >= store.prefetch.total && store.prefetch.total > 0
);

async function plan() {
  loading.value = true;
  try {
    const plan = await store.create(req);
    const urls = (plan.assets || []).map(a => a.audio?.url).filter(Boolean);
    store.setPrefetchProgress(urls.length, 0);

    await new Promise((resolve, reject) => {
      const ch = new MessageChannel();
      ch.port1.onmessage = (e) => (e.data && e.data.ok ? resolve() : reject(new Error("prefetch failed")));
      if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ type: "PREFETCH_PACK_ASSETS", urls }, [ch.port2]);
      } else {
        // ページを一度リロードすると controller が付くことがあります
        reject(new Error("no service worker controller"));
      }
    });
    store.setPrefetchProgress(urls.length, urls.length);
  } catch (e) {
    store.setPrefetchState(false, e?.message || String(e));
    return;
  } finally {
    store.setPrefetchState(false);
    loading.value = false;
  }
}
</script>

<style scoped>
/* 既存UIの雰囲気：角丸・薄い影・控えめな余白 */
</style>
