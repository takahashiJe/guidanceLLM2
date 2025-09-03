import { defineStore } from 'pinia';
import { openDB } from 'idb';
import { createPlan, fetchPlanTask } from '@/lib/api';

const DB_NAME = 'navpacks';
const DB_STORE = 'plans';

async function getDB() {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(DB_STORE)) {
        db.createObjectStore(DB_STORE, { keyPath: 'pack_id' });
      }
    },
  });
}

function haversine(a, b) {
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const x = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.sqrt(x));
}

async function playFromCacheOrNetwork(url, packId) {
  const cache = await caches.open(`packs-${packId}`);
  const cached = await cache.match(url);
  const src = cached ? URL.createObjectURL(await cached.blob()) : url;
  const audio = new Audio(src);
  await audio.play().catch(()=>{});
}

export const useNavStore = defineStore('nav', {
  state: () => ({
    lang: 'ja',
    waypoints: [],          // ['spot_001','spot_007',...]
    taskId: null,
    plan: null,             // PlanResponse
    watchingId: null,       // geolocation watch id
    triggered: new Set(),   // 再生済みspot
    proximityMeters: 250,   // 近接閾値（初期:車運用向け）
  }),
  getters: {
    packId: (s) => s.plan?.pack_id || null,
  },
  actions: {
    setLang(l) { this.lang = l; },
    setWaypoints(list) { this.waypoints = list; },

    async submitPlan(origin) {
      if (!this.waypoints.length) throw new Error('waypoints is empty');
      const payload = {
        language: this.lang,
        origin,
        return_to_origin: true,
        waypoints: this.waypoints.map(id => ({ spot_id: id })),
      };
      const res = await createPlan(payload);
      this.taskId = res.task_id;
      return res;
    },

    async pollUntilReady(intervalMs = 1500, timeoutMs = 120000) {
      const start = Date.now();
      while (true) {
        const { status, body } = await fetchPlanTask(this.taskId);
        if (status === 200) {
          this.plan = body;
          // 保存
          const db = await getDB();
          await db.put(DB_STORE, body);
          // プリフェッチ
          await this.prefetchAssets();
          return body;
        }
        if (status === 500) throw new Error(`plan failed: ${JSON.stringify(body)}`);
        if (Date.now() - start > timeoutMs) throw new Error('plan polling timeout');
        await new Promise(r => setTimeout(r, intervalMs));
      }
    },

    async prefetchAssets() {
      if (!this.plan?.assets?.length) return;
      const packId = this.packId;
      const cache = await caches.open(`packs-${packId}`);
      await Promise.all(
        this.plan.assets
          .map(a => a?.audio?.url)
          .filter(Boolean)
          .map(u => cache.add(new Request(u, { mode: 'same-origin' })))
      );
    },

    async restorePlan(packId) {
      const db = await getDB();
      const plan = await db.get(DB_STORE, packId);
      if (plan) this.plan = plan;
      return plan;
    },

    startProximityWatcher() {
      if (!this.plan) return;
      if (this.watchingId) navigator.geolocation.clearWatch(this.watchingId);

      const onPos = async (pos) => {
        const cur = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        const allSpots = [
          ...(this.plan.along_pois || []),
        ];
        // waypointsを along_pois に含めない設計なら、ここで追加しても良い（必要に応じて）
        // ※ spot_repo の定義次第。今は along_pois に含まれている前提でもOK。

        for (const s of allSpots) {
          if (!s?.spot_id || this.triggered.has(s.spot_id)) continue;
          const d = haversine(cur, { lat: s.lat, lon: s.lon });
          if (d <= this.proximityMeters) {
            // 近接トリガ
            const asset = this.plan.assets.find(a => a.spot_id === s.spot_id);
            if (asset?.audio?.url) {
              this.triggered.add(s.spot_id);
              await playFromCacheOrNetwork(asset.audio.url, this.packId);
            }
          }
        }
      };

      const onErr = () => {};
      this.watchingId = navigator.geolocation.watchPosition(onPos, onErr, {
        enableHighAccuracy: true,
        maximumAge: 5000,
        timeout: 10000,
      });
    },

    stopProximityWatcher() {
      if (this.watchingId) navigator.geolocation.clearWatch(this.watchingId);
      this.watchingId = null;
    },
  },
});
