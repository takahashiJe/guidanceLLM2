// src/lib/tiles.js
export const TILE_TEMPLATE = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
export const TILE_SUBS = ['a', 'b', 'c'];

// Leaflet のテンプレと一致するURLを生成
export function tileUrl(z, x, y, sIdx = 0) {
  const s = TILE_SUBS[sIdx % TILE_SUBS.length];
  return `https://${s}.tile.openstreetmap.org/${z}/${x}/${y}.png`;
}

// ルート（polyline: [[lon,lat], ...]）の外接BBoxを元に、複数ズームのタイルを事前取得
export async function prefetchTilesForRoute(polyline, opts = {}) {
  const { zooms = [12, 13, 14, 15], marginDeg = 0.05, max = 800 } = opts;
  if (!Array.isArray(polyline) || polyline.length === 0) return 0;

  let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
  for (const [lon, lat] of polyline) {
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
  }
  minLat -= marginDeg; maxLat += marginDeg; minLon -= marginDeg; maxLon += marginDeg;

  const cache = await caches.open('tiles-v1');
  let count = 0, s = 0;

  for (const z of zooms) {
    const xMin = lon2tile(minLon, z), xMax = lon2tile(maxLon, z);
    const yMin = lat2tile(maxLat, z), yMax = lat2tile(minLat, z);
    for (let x = xMin; x <= xMax; x++) {
      for (let y = yMin; y <= yMax; y++) {
        const url = tileUrl(z, x, y, s++);
        if (count >= max) return count;
        try {
          const res = await fetch(url, { mode: 'no-cors' }); // opaque OK
          await cache.put(url, res.clone());
          count++;
        } catch { /* ignore */ }
      }
    }
  }
  return count;
}

function lon2tile(lon, z) {
  return Math.floor((lon + 180) / 360 * Math.pow(2, z));
}
function lat2tile(lat, z) {
  const rad = lat * Math.PI / 180;
  return Math.floor((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2 * Math.pow(2, z));
}
