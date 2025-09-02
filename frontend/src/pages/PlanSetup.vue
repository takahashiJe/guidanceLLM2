<template>
  <div class="page plan-setup">
    <header class="header">
      <h1>周遊プランの準備</h1>
    </header>

    <main class="content">
      <!-- シンプルな入力。実際はスポットピッカーに置換想定 -->
      <div class="card">
        <label class="row">
          言語：
          <select v-model="lang">
            <option value="ja">日本語</option>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </label>

        <label class="row">
          復路：<input type="checkbox" v-model="returnToOrigin" />
        </label>

        <button class="primary" :disabled="loading" @click="onCreate">
          {{ loading ? "作成中…" : "プラン作成" }}
        </button>
      </div>

      <p class="hint">Wi-Fi 下で音声を事前取得します．</p>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { usePlanStore } from "@/stores/plan";
import { useAssetsStore } from "@/stores/assets";
import { ensureSW } from "@/lib/sw";

const router = useRouter();
const planStore = usePlanStore();
const assetsStore = useAssetsStore();

const lang = ref("ja");
const returnToOrigin = ref(true);
const loading = ref(false);

onMounted(async () => {
  await ensureSW(); // SWを先に登録
});

async function onCreate() {
  loading.value = true;
  try {
    // デモ用：ダミーのwaypoints（本実装ではUIから取得）
    const req = {
      language: lang.value,
      return_to_origin: returnToOrigin.value,
      waypoints: [
        { spot_id: "current", lat: 39.2, lon: 139.9 },
        { spot_id: "A", lat: 39.3, lon: 139.95 },
        { spot_id: "B", lat: 39.35, lon: 139.98 },
        { spot_id: "C", lat: 39.25, lon: 139.96 },
        { spot_id: "current", lat: 39.2, lon: 139.9 },
      ],
      buffers: { car: 300, foot: 10 },
    };

    const plan = await planStore.loadPlanFromApi(req);
    // すぐプリフェッチ開始 → 進捗画面へ
    assetsStore.reset();
    router.push(`/prefetch/${plan.pack_id}`);
  } catch (e) {
    alert("プラン作成に失敗しました．Wi-Fi 接続を確認してください．");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.page { min-height: 100vh; background: #0e0f12; color: #fff; }
.header { padding: 16px; font-weight: 700; }
.content { padding: 16px; }
.card { background: #16181d; border-radius: 16px; padding: 16px; }
.row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.primary { width: 100%; padding: 14px; border-radius: 12px; background: #3b82f6; color: #fff; border: none; font-weight: 700; }
.hint { opacity: 0.8; margin-top: 12px; font-size: 13px; }
</style>
