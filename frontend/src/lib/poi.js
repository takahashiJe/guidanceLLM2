// src/lib/poi.js
// POI一覧を取得して {spot_id, name, lat, lon, names?} の配列に正規化する。

/**
 * まずフロントの /public/pois.json（配信時は /<base>/pois.json）を最優先で読みに行く。
 * 成功しなければ API 候補を順に試す。
 * 必要なら VITE_POIS_URL で固定URLを指定できる。
 */
const FRONT_POIS =
  (import.meta.env.BASE_URL || '/') + 'pois.json';

const API_CANDIDATES = [
  '/back/api/nav/pois',
  '/back/api/pois',
  '/back/api/poi',
];

// 明示URLがあればそれを最優先に
const EXPLICIT = import.meta.env.VITE_POIS_URL
  ? [import.meta.env.VITE_POIS_URL]
  : [];

const CANDIDATES = [
  ...EXPLICIT,
  FRONT_POIS,          // ← ここを最初に試す
  ...API_CANDIDATES,
];

async function tryFetchJson(url) {
  try {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchPois() {
  let raw = null, src = null;

  for (const url of CANDIDATES) {
    raw = await tryFetchJson(url);
    if (raw) { src = url; break; }
  }

  if (!raw) {
    console.warn('[poi] 取得に失敗（candidates=', CANDIDATES, '）');
    return [];
  }

  const arr = Array.isArray(raw) ? raw
    : (Array.isArray(raw.items) ? raw.items
    : (Array.isArray(raw.features) ? raw.features : []));

  const list = arr.map(normalizePoi).filter(Boolean);
  // console.debug('[poi] loaded', list.length, 'from', src);
  return list;
}

// 各形式を吸収して { spot_id, name, lat, lon, names? } に統一
function normalizePoi(p) {
  // GeoJSON Feature?
  if (p && p.type === 'Feature') {
    const props = p.properties || {};
    const id =
      props.spot_id ?? props.id ?? p.id ?? null;
    const names =
      props.official_name ?? props.names ?? null;
    const display =
      props.name_ja ?? props.name ?? pickName(names) ?? id;

    const coords = p.geometry?.coordinates;
    const lat = coords ? +coords[1] : (props.lat ?? null);
    const lon = coords ? +coords[0] : (props.lon ?? null);

    return id ? { spot_id: String(id), name: String(display), lat, lon, names } : null;
  }

  const id = p.spot_id ?? p.id ?? p.code ?? p.slug ?? null;
  if (!id) return null;

  const names = p.official_name ?? p.names ?? null;
  const display = p.name_ja ?? p.name?.ja ?? p.name ?? p.title ?? pickName(names) ?? String(id);

  const lat = p.lat ?? p.latitude ?? p.point?.lat ?? p.coordinates?.[1] ?? null;
  const lon = p.lon ?? p.lng ?? p.longitude ?? p.point?.lon ?? p.coordinates?.[0] ?? null;

  return {
    spot_id: String(id),
    name: String(display),
    lat: lat != null ? +lat : null,
    lon: lon != null ? +lon : null,
    names
  };
}

// {ja,en,zh,…} のどれかから表示名を拾う（優先: ja→en→zh）
function pickName(names) {
  if (!names || typeof names !== 'object') return null;
  return names.ja || names.en || names.zh || null;
}
