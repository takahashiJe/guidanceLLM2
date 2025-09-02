<template>
  <div id="app" class="app-root">
    <!-- ページがここに差し込まれる -->
    <router-view />
  </div>
</template>

<script setup>
// 特別なロジックは不要
</script>

<style>
/* アプリ全体の基本スタイル */
.app-root {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0e0f12; /* ダーク背景（添付UIに合わせる） */
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, "Noto Sans JP", sans-serif;
}

/* リンクやボタンのタップ領域を強調 */
a {
  color: #3b82f6;
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}

/* ボタンのベーススタイル */
button {
  font: inherit;
  cursor: pointer;
  border: none;
  border-radius: 12px;
  padding: 10px 16px;
}
</style>
