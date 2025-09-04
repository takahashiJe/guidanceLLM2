<!-- src/views/NavView.vue -->
<template>
  <div class="page">
    <header class="topbar">
      <router-link to="/plan" class="link">プランへ</router-link>
      <div class="title">ナビ中</div>
      <div class="tiny">#{{ packShort }}</div>
    </header>

    <NavMap
      v-if="plan"
      :plan="plan"
      :lang="store.lang"
    />
    <div v-else class="empty">計画を読み込み中…</div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useNavStore } from '@/stores/nav';
import NavMap from '@/components/NavMap.vue';

const store = useNavStore();
const plan = computed(() => store.plan);
const packShort = computed(() => (plan.value?.pack_id || '').slice(-8));
</script>

<style scoped>
.page { width:100%; height:100vh; display:flex; flex-direction:column; }
.topbar { height:48px; display:flex; align-items:center; justify-content:space-between;
  padding:0 12px; border-bottom:1px solid #eee; font-size:16px; }
.link { color:#1976d2; text-decoration:none; }
.title { font-weight:600; }
.tiny { color:#888; font-family:monospace; }
.empty { padding:24px; color:#666; }
</style>
