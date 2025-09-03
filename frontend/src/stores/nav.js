// src/stores/nav.js
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
  try { await audio.play(); } catch (_) {}
}

export const useNavStore = defineStore('nav', {
  state: () => ({
    lang: 'ja',
    waypoints: [],
    taskId: null,
    plan: null,
    watchingId: null,
    triggered: new Set(),
    proximityMeters: 250,
    polling: false,
    pollLog: [],
  }),
  getters: {
    packId: (s) => s.plan?.pack_id || null,
  },
  actions: {
    setLang(l) { this.lang = l; },
    setWaypoints(list) { this.waypoints = list; },

    async submitPlan(origin) {
      console.log('[nav] submitPlan origin=', origin, 'lang=', this.lang, 'wps=', this.waypoints);
      if (!this.waypoints.length) throw new Error('waypoints is empty');
      const payload = {
        language: this.lang,
        origin,
        return_to_origin: true,
        waypoints: this.waypoints.map(id => ({ spot_id: id })),
      };
      const res = await createPlan(payload);
      this.taskId = res.task_id;
      console.log('[nav] taskId=', this.taskId);
      // 自動でポーリング開始
      this.pollUntilReady().catch(err => {
        console.error('[nav] poll error:', err);
        this.pollLog.push(`ERROR: ${err.message || err}`);
      });
      return res;
    },

    async pollUntilReady(intervalMs = 1500, timeoutMs = 120000) {
      if (!this.taskId) throw new Error('taskId is empty');
      const start = Date.now();
      this.polling = true;
      this.pollLog = [];
      console.log('[nav] start polling taskId=', this.taskId);

      while (true) {
        const { status, body } = await fetchPlanTask(this.taskId);
        this.pollLog.push(`status=${status} ${new Date().toLocaleTimeString()}`);
        console.log('[nav] poll status', status, body ? '(body received)' : '');

        if (status === 200) {
          this.plan = body;
          const db = await getDB();
          await db.put(DB_STORE, body);
          await this.prefetchAssets();
          this.polling = false;
          console.log('[nav] READY pack=', this.plan?.pack_id);
          return body;
        }

        if (status === 500) {
          this.polling = false;
          throw new Error(`plan failed: ${JSON.stringify(body)}`);
        }

        if (Date.now() - start > timeoutMs) {
          this.polling = false;
          throw new Error('plan polling timeout');
        }

        await new Promise(r => setTimeout(r, intervalMs));
      }
    },

    async prefetchAssets() {
      if (!this.plan?.assets?.length) return;
      const packId = this.packId;
      const cache = await caches.open(`packs-${packId}`);
      console.log('[nav] prefetch assets for pack', packId);
      await Promise.all(
        this.plan.assets
          .map(a => a?.audio?.url)
          .filter(Boolean)
          .map(u => cache.add(new Request(u, { mode: 'same-origin' })))
      );
      console.log('[nav] prefetch done');
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
        const allSpots = [ ...(this.plan.along_pois || []) ];
        for (const s of allSpots) {
          if (!s?.spot_id || this.triggered.has(s.spot_id)) continue;
          const d = haversine(cur, { lat: s.lat, lon: s.lon });
          if (d <= this.proximityMeters) {
            const asset = this.plan.assets.find(a => a.spot_id === s.spot_id);
            if (asset?.audio?.url) {
              this.triggered.add(s.spot_id);
              await playFromCacheOrNetwork(asset.audio.url, this.packId);
            }
          }
        }
      };

      const onErr = (e) => { console.warn('[nav] geolocation error', e); };
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
