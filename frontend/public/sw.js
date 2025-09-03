const APP_CACHE = 'app-shell-v1';
const APP_ASSETS = [
  '/', '/index.html',
  '/favicon.ico',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(APP_CACHE).then(c => c.addAll(APP_ASSETS)));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== APP_CACHE).map(k => caches.delete(k)))
    )
  );
});

// ルートや静的はキャッシュ優先、APIや /packs/ はページ側で制御する方針
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  const isApp = url.origin === location.origin && !url.pathname.startsWith('/back/');
  if (isApp) {
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request))
    );
  }
});
