// src/lib/poi.js
// POI一覧を最初にヒットしたソースから取得し、UIで使いやすい形に正規化します。
// 優先順: API(いくつかの候補) → フロントの /public/pois.json
const CANDIDATES = [
  '/back/api/nav/pois',  // もし実装済みなら最優先
  '/back/api/pois',
  '/back/api/poi',
  '/back/static/POI.json',
  '/back/static/poi.json',
  '/pois.json',          // フロントの public/pois.json に配置した場合
];

export async function fetchPois() {
  let raw = null, src = null, lastErr = null;
  for (const p of CANDIDATES) {
    try {
      const res = await fetch(p, { headers: { 'Accept': 'application/json' } });
      if (!res.ok) continue;
      raw = await res.json();
      src = p;
      break;
    } catch (e) {
      lastErr = e;
    }
  }
  if (!raw) {
    console.warn('[poi] 取得に失敗: ', lastErr);
    return [];
  }
  const arr = Array.isArray(raw) ? raw
    : (Array.isArray(raw.items) ? raw.items
    : (Array.isArray(raw.features) ? raw.features : []));

  const list = arr.map(normalizePoi).filter(Boolean);
  console.debug('[poi] loaded', list.length, 'from', src);
  return list;
}

// 可能な限り { spot_id, name, lat, lon } に合わせる（フィールド名が違っても吸収）
function normalizePoi(p) {
  // GeoJSON Feature?
  if (p && p.type === 'Feature') {
    const id = p.properties?.spot_id || p.properties?.id || p.id;
    const name = p.properties?.name_ja || p.properties?.name || id;
    const coords = p.geometry?.coordinates;
    return id ? {
      spot_id: String(id),
      name: String(name || id),
      lat: coords ? +coords[1] : (p.properties?.lat ?? null),
      lon: coords ? +coords[0] : (p.properties?.lon ?? null),
    } : null;
  }
  const id =
    p.spot_id ?? p.id ?? p.code ?? p.slug ?? null;
  if (!id) return null;
  const name =
    p.name_ja ?? p.name?.ja ?? p.name ?? p.title ?? String(id);
  const lat = p.lat ?? p.latitude ?? p.point?.lat ?? p.coordinates?.[1] ?? null;
  const lon = p.lon ?? p.lng ?? p.longitude ?? p.point?.lon ?? p.coordinates?.[0] ?? null;
  return { spot_id: String(id), name: String(name), lat: lat != null ? +lat : null, lon: lon != null ? +lon : null };
}
