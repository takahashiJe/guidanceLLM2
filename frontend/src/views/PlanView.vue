<!-- src/views/PlanView.vue -->
<template>
  <div class="page">
    <header class="bar">
      <h1>ナビ計画</h1>
    </header>

    <main class="content">
      <PlanForm @submit="onSubmit" :submitting="submitting" />
      <p v-if="error" class="error">エラー: {{ errorMsg }}</p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useNavStore } from '@/stores/nav';
import PlanForm from '@/components/PlanForm.vue';

const router = useRouter();
const nav = useNavStore();

const submitting = ref(false);
const error = ref(null);
const errorMsg = computed(() => (error.value?.message || '不明なエラー'));

function normalizePayload(v) {
  // v: { language, origin:{lat|lng|lon}, waypoints:[string|{spot_id}] }
  const lang = (v?.language || 'ja');
  const lat = Number(v?.origin?.lat);
  // フォームが lng を出すことがあるので lon 優先で fallback lng
  const lon = Number(
    v?.origin?.lon ?? v?.origin?.lng
  );
  const waypoints = (v?.waypoints || [])
    .map(w => (typeof w === 'string' ? { spot_id: w } : w))
    .filter(x => x && x.spot_id);

  return {
    language: ['ja','en','zh'].includes(lang) ? lang : (lang === 'zh-CN' || lang === 'cn' ? 'zh' : 'ja'),
    origin: { lat, lon },
    return_to_origin: true,
    waypoints,
  };
}

async function onSubmit(formValue) {
  error.value = null;
  submitting.value = true;
  try {
    // UI状態にも反映（戻って来たときの再編集用）
    nav.setLang(formValue.language);
    nav.setOrigin({
      lat: Number(formValue?.origin?.lat),
      lon: Number(formValue?.origin?.lon ?? formValue?.origin?.lng),
    });
    nav.setWaypoints(formValue.waypoints);

    // サーバ用にスキーマ正規化
    const payload = normalizePayload(formValue);

    // 送信ワンストップ
    await nav.submitPlan(payload);

    // 完了後に /nav へ
    router.push('/nav');
  } catch (e) {
    console.error('[plan] submit error', e, e?.body);
    // 422 のときはサーバの detail も表示
    if (e?.status === 422 && e?.body?.detail) {
      e.message = '入力が不正です: ' + JSON.stringify(e.body.detail);
    }
    error.value = e;
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; height: 100dvh; }
.bar { padding: 12px; border-bottom: 1px solid #eee; }
.content { padding: 12px; }
.error { color: #c00; margin-top: 8px; word-break: break-all; }
</style>
