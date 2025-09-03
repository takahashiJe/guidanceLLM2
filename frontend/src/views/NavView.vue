<!-- src/views/NavView.vue -->
<template>
  <div class="page">
    <header class="bar">
      <button class="link" @click="goPlan">プランへ</button>
      <div class="title">ナビ中</div>
      <div class="pack" v-if="nav.packId">#{{ nav.packId.slice(0,8) }}</div>
    </header>

    <main class="mapwrap">
      <NavMap :plan="nav.plan" />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';
import { useNavStore } from '@/stores/nav';
import NavMap from '@/components/NavMap.vue';

const router = useRouter();
const nav = useNavStore();

function goPlan() {
  router.push('/plan');
}
</script>

<style scoped>
.page { display:flex; flex-direction:column; height:100dvh; }
.bar {
  display:flex; align-items:center; gap:8px;
  padding:10px; border-bottom:1px solid #eee;
}
.link { background:none; border:none; color:#06f; font-size:16px; }
.title { font-weight:600; flex:1; text-align:center; }
.pack { font-size:12px; color:#666; }
.mapwrap { flex:1; }
</style>
