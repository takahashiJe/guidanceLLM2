// public/sw.js

self.addEventListener('install', (event) => {
  // 旧キャッシュを残さない
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// fetch: /back/ は完全に素通し（キャッシュしない）
//       /packs/ も基本ネット優先（Cache Storage への事前プリフェッチはアプリ側が行う）
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/back/')) {
    return; // SW で触らない（ブラウザに任せる）
  }
  if (url.pathname.startsWith('/packs/')) {
    // 音声はブラウザ既定の挙動に任せる（アプリ側で caches.add するため）
    return;
  }
  // それ以外は通常通り（必要なら静的アセットのキャッシュ戦略を追加）
});
