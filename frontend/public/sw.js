// public/sw.js
// v2 — packs(音声)のRange対応 + OSMタイルのオフライン対応
self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(self.clients.claim()); });

const PACKS_PREFIX = 'packs-';
const TILES_CACHE  = 'tiles-v1';
const RUNTIME      = 'runtime';

// タイルの許可ホスト（OSM公式）
const TILE_HOSTS = [
  'tile.openstreetmap.org',
  'a.tile.openstreetmap.org',
  'b.tile.openstreetmap.org',
  'c.tile.openstreetmap.org',
];

const EMPTY_TILE_PNG = (() => {
  // 透明1x1 PNG（tileサイズとは無関係・ブラウザ側で拡大される）
  const base64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8m2k4AAAAASUVORK5CYII=';
  return new Response(Uint8Array.from(atob(base64), c => c.charCodeAt(0)), {
    status: 200,
    headers: { 'Content-Type': 'image/png', 'Cache-Control': 'public, max-age=31536000' }
  });
})();

async function latestPacksCacheName() {
  const names = await caches.keys();
  const packs = names.filter(n => n.startsWith(PACKS_PREFIX)).sort();
  return packs.slice(-1)[0] || RUNTIME;
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 音声（/packs/…）— Range対応
  if (url.origin === self.location.origin && url.pathname.startsWith('/packs/')) {
    event.respondWith(handlePacks(req));
    return;
  }

  // OSMタイル（クロスオリジン）— キャッシュ or 透過タイルでフォールバック
  if (req.method === 'GET'
      && req.destination === 'image'
      && TILE_HOSTS.includes(url.host)
      && url.pathname.endsWith('.png')) {
    event.respondWith(handleTiles(req));
    return;
  }

  // それ以外は素通し
});

async function handlePacks(request) {
  const cache = await caches.open(await latestPacksCacheName());
  let res = await cache.match(request, { ignoreSearch: true });

  if (!res) {
    try {
      res = await fetch(request);
      try { await cache.put(request, res.clone()); } catch {}
    } catch {
      return new Response('Offline and not cached', { status: 504 });
    }
  }

  // Range ヘッダが来たら部分応答を自前で生成
  const range = request.headers.get('Range');
  if (range) {
    const full = await res.clone().blob();
    const size = full.size;
    const m = /bytes=(\d+)-(\d+)?/.exec(range);
    if (m) {
      const start = Number(m[1]);
      const end = m[2] ? Number(m[2]) : size - 1;
      const sliced = full.slice(start, end + 1);
      return new Response(sliced, {
        status: 206,
        headers: {
          'Content-Type': res.headers.get('Content-Type') || 'audio/mpeg',
          'Content-Range': `bytes ${start}-${end}/${size}`,
          'Accept-Ranges': 'bytes',
          'Content-Length': String(end - start + 1),
          'Cache-Control': 'public, max-age=31536000',
        },
      });
    }
  }
  return res;
}

async function handleTiles(request) {
  const cache = await caches.open(TILES_CACHE);
  const cached = await cache.match(request, { ignoreSearch: true });
  if (cached) {
    // SWR（裏で更新）
    fetch(request).then(res => { try { cache.put(request, res.clone()); } catch {} }).catch(()=>{});
    return cached;
  }
  try {
    const res = await fetch(request, { mode: 'no-cors' }); // opaque 可
    try { await cache.put(request, res.clone()); } catch {}
    trimTilesCache(cache).catch(()=>{});
    return res;
  } catch {
    return EMPTY_TILE_PNG.clone();
  }
}

const MAX_TILES = 1500; // 約〜50MB目安（環境により増減させてOK）
async function trimTilesCache(cache) {
  const keys = await cache.keys();
  if (keys.length > MAX_TILES) {
    const del = keys.length - MAX_TILES;
    for (let i = 0; i < del; i++) { await cache.delete(keys[i]); }
  }
}
