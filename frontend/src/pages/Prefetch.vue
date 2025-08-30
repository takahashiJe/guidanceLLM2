<template>
  <div class="page prefetch">
    <header class="header"><h1>事前取得</h1></header>
    <main class="content">
      <div class="card">
        <p>音声ファイルをキャッシュしています…</p>
        <p v-if="state==='running'">取得中：{{ done }}/{{ total }}</p>
        <p v-if="state==='done'">完了しました．</p>
        <p v-if="state==='error'">一部取得に失敗しました：{{ error }}</p>
      </div>
      <button class="primary" :disabled="state!=='done'" @click="goNav">
        ナビ開始
      </button>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { usePlanStore } from "@/stores/plan";
import { useAssetsStore } from "@/stores/assets";

const route = useRoute();
const router = useRouter();
const planStore = usePlanStore();
const assetsStore = useAssetsStore();

const total = computed(() => assetsStore.prefetch.total);
const done = computed(() => assetsStore.prefetch.done);
const state = computed(() => assetsStore.prefetch.state);
const error = computed(() => assetsStore.prefetch.error);

onMounted(async () => {
  if (!planStore.plan) return;
  await assetsStore.prefetchAll(planStore.plan.assets || []);
});

function goNav() {
  router.push(`/nav/${route.params.packId}`);
}
</script>

<style scoped>
.page { min-height: 100vh; background: #0e0f12; color: #fff; }
.header { padding: 16px; font-weight: 700; }
.content { padding: 16px; }
.card { background: #16181d; border-radius: 16px; padding: 16px; margin-bottom: 12px; }
.primary { width: 100%; padding: 14px; border-radius: 12px; background: #10b981; color: #0b1220; border: none; font-weight: 700; }
</style>
