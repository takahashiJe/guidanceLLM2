<template>
  <div class="app">
    <header class="appbar">
      <RouterLink to="/plan" class="btn">プランへ</RouterLink>
      <RouterLink to="/nav" class="btn">ナビへ</RouterLink>
    </header>
    <main class="page">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
// ここは何も不要。RouterLink/RouterView はグローバル。
</script>

<style>
:root { --gap: 12px; }
* { box-sizing: border-box; }
html, body, #app { height: 100%; margin: 0; }
.appbar {
  position: sticky; top: 0; z-index: 1000;
  display: flex; gap: var(--gap);
  padding: 10px 12px;
  background: #fff; border-bottom: 1px solid #eee;
}
.btn {
  padding: 8px 12px; border: 1px solid #ddd; border-radius: 10px;
  text-decoration: none; color: #222; background: #fafafa;
}
.page { padding: var(--gap); }
@media (max-width: 480px) {
  .page { padding: 8px; }
}
</style>
