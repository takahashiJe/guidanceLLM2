// src/lib/poi.js
// 自然スポット（POI）と施設のメタデータを正規化して提供する

import facilitiesCatalogRaw from '@/assets/facilities.json'
import poisCatalogRaw from '@/assets/POI.json'

export function fetchPois() {
  const arr = Array.isArray(poisCatalogRaw) ? poisCatalogRaw
    : (Array.isArray(poisCatalogRaw.items) ? poisCatalogRaw.items
    : (Array.isArray(poisCatalogRaw.features) ? poisCatalogRaw.features : []))

  const list = arr.map((item) => normalizePoi(item, { kind: 'spot' })).filter(Boolean)
  return dedupeBySpotId(list)
}

// 施設はビルド時にバンドルされるため同期で展開する
const FACILITY_LIST = Array.isArray(facilitiesCatalogRaw)
  ? facilitiesCatalogRaw.map((item) => normalizePoi(item, { kind: 'facility' })).filter(Boolean)
  : []

export function getFacilities() {
  // 呼び出し側で安全に使えるようコピーを返す
  return FACILITY_LIST.map((item) => ({ ...item }))
}

export function fetchPoiCatalog({ includeFacilities = true } = {}) {
  const spots = fetchPois()
  if (!includeFacilities) {
    return spots
  }

  const merged = dedupeBySpotId([...spots, ...FACILITY_LIST])
  return merged
}

function dedupeBySpotId(entries) {
  const map = new Map()
  for (const entry of entries) {
    if (!entry || !entry.spot_id) continue
    if (!map.has(entry.spot_id)) {
      map.set(entry.spot_id, entry)
    }
  }
  return Array.from(map.values())
}

function toNumber(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

function extractLat(p) {
  if (p.lat != null) return toNumber(p.lat)
  if (p.latitude != null) return toNumber(p.latitude)
  if (p.point?.lat != null) return toNumber(p.point.lat)
  if (Array.isArray(p.coordinates)) return toNumber(p.coordinates[1])
  if (p.coordinates && typeof p.coordinates === 'object') {
    if (p.coordinates.lat != null) return toNumber(p.coordinates.lat)
    if (p.coordinates.latitude != null) return toNumber(p.coordinates.latitude)
  }
  return null
}

function extractLon(p) {
  if (p.lon != null) return toNumber(p.lon)
  if (p.lng != null) return toNumber(p.lng)
  if (p.longitude != null) return toNumber(p.longitude)
  if (p.point?.lon != null) return toNumber(p.point.lon)
  if (Array.isArray(p.coordinates)) return toNumber(p.coordinates[0])
  if (p.coordinates && typeof p.coordinates === 'object') {
    if (p.coordinates.lon != null) return toNumber(p.coordinates.lon)
    if (p.coordinates.longitude != null) return toNumber(p.coordinates.longitude)
  }
  return null
}

// 各形式を吸収して { spot_id, name, lat, lon, names?, kind?, md_slug? } に統一
function normalizePoi(p, overrides = {}) {
  // GeoJSON Feature?
  if (p && p.type === 'Feature') {
    const props = p.properties || {}
    const id =
      props.spot_id ?? props.id ?? p.id ?? null
    const names =
      props.official_name ?? props.names ?? null
    const display =
      props.name_ja ?? props.name ?? pickName(names) ?? id

    const coords = p.geometry?.coordinates
    const lat = coords ? toNumber(coords[1]) : extractLat(props)
    const lon = coords ? toNumber(coords[0]) : extractLon(props)

    if (!id) return null
    return finalizeEntry({
      spot_id: String(id),
      name: String(display),
      lat,
      lon,
      names,
      md_slug: props.md_slug ?? null,
      kind: props.kind ?? overrides.kind ?? 'spot',
      category: props.category ?? overrides.category ?? null,
    })
  }

  const id = p.spot_id ?? p.id ?? p.code ?? p.slug ?? null
  if (!id) return null

  const names = p.official_name ?? p.names ?? null
  const display = p.name_ja ?? p.name?.ja ?? p.name ?? p.title ?? pickName(names) ?? String(id)

  const lat = extractLat(p)
  const lon = extractLon(p)

  return finalizeEntry({
    spot_id: String(id),
    name: String(display),
    lat,
    lon,
    names,
    md_slug: p.md_slug ?? null,
    kind: p.kind ?? overrides.kind ?? 'spot',
    category: p.category ?? overrides.category ?? null,
  })
}

// {ja,en,zh,…} のどれかから表示名を拾う（優先: ja→en→zh）
function pickName(names) {
  if (!names || typeof names !== 'object') return null
  return names.ja || names.en || names.zh || null
}

function finalizeEntry(entry) {
  const { lat, lon } = entry
  return {
    ...entry,
    lat: toNumber(lat),
    lon: toNumber(lon),
  }
}
