self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

async function prefetch(urls) {
  const cache = await caches.open("packs");
  // まとめて取れない場合もあるので逐次
  for (const u of urls || []) {
    try { await cache.add(u); } catch (e) { /* 個別失敗は無視 */ }
  }
}

self.addEventListener("message", async (e) => {
  const { type, payload } = e.data || {};
  if (type === "PREFETCH_ASSETS") {
    try {
      await prefetch(payload?.urls || []);
      e.ports[0]?.postMessage({ ok: true, count: (payload?.urls || []).length });
    } catch {
      e.ports[0]?.postMessage({ ok: false, count: 0 });
    }
  }
});
