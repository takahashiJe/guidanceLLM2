// src/stores/nav.js
import { defineStore } from 'pinia';
import { openDB } from 'idb';
import { createPlan, pollPlan } from '@/lib/api';

const DB_NAME = 'navpacks';
const DB_VER = 1;
const STORE   = 'plans';

async function getDB() {
  return openDB(DB_NAME, DB_VER, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    }
  });
}

export const useNavStore = defineStore('nav', {
  state: () => ({
    // UI入力保持
    lang: 'ja',
    origin: { lat: 39.2201, lon: 139.9006 },
    waypointIds: [],

    // 実行・結果
    plan: null,
    packId: null,
    polling: false,
    ready: false,
    error: null,
  }),
  getters: {
    hasPlan: (s) => !!s.plan,
  },
  actions: {
    // ====== UI設定系 ======
    setLang(lang) {
      // サーバは "ja" | "en" | "zh"
      const m = { ja: 'ja', en: 'en', zh: 'zh', 'zh-CN': 'zh', cn: 'zh' };
      this.lang = m[lang] || 'ja';
    },
    setOrigin({ lat, lon }) {
      const latNum = Number(lat);
      const lonNum = Number(lon);
      if (Number.isFinite(latNum) && Number.isFinite(lonNum)) {
        this.origin = { lat: latNum, lon: lonNum };
      }
    },
    setWaypoints(ids) {
      this.waypointIds = Array.isArray(ids) ? ids.filter(Boolean) : [];
    },

    // ====== Plan 反映系 ======
    setPlan(plan) {
      this.plan = plan;
      this.packId = plan?.pack_id || null;
      this.ready = !!plan;
      this.error = null;
    },
    clearPlan() {
      this.plan = null;
      this.packId = null;
      this.ready = false;
      this.error = null;
    },

    // ====== IndexedDB ======
    async savePlanToDB(plan) {
      const db = await getDB();
      await db.put(STORE, plan, plan.pack_id);
    },
    async loadPlanFromDB(packId) {
      const db = await getDB();
      const plan = await db.get(STORE, packId);
      if (plan) this.setPlan(plan);
      return plan;
    },

    // ====== プリフェッチ ======
    async prefetchAssets() {
      if (!this.plan) return;
      const cache = await caches.open(`packs-${this.packId}`);
      const urls = (this.plan.assets || [])
        .map(a => a?.audio?.url)
        .filter(Boolean);
      await Promise.all(urls.map(u => cache.add(new Request(u, { mode: 'no-cors' }))));
    },

    // ====== 送信ワンストップ ======
    async submitPlan(payload) {
      // payload は PlanRequest 形式に正規化して送る（PlanView側でも正規化するが念のためここでも型を保証）
      const req = {
        language: (payload?.language || this.lang),
        origin: {
          lat: Number(payload?.origin?.lat ?? this.origin.lat),
          lon: Number(payload?.origin?.lon ?? this.origin.lon),
        },
        return_to_origin: Boolean(
          payload?.return_to_origin ?? true
        ),
        waypoints: (payload?.waypoints || this.waypointIds || [])
          .map(w => (typeof w === 'string' ? { spot_id: w } : w))
          .filter(x => x && x.spot_id),
      };

      this.error = null;
      this.polling = true;
      this.ready = false;
      try {
        const { task_id } = await createPlan(req);
        const plan = await pollPlan(task_id, () => {});
        this.setPlan(plan);
        await this.savePlanToDB(plan);
        await this.prefetchAssets();
        this.ready = true;
        return plan;
      } catch (e) {
        this.error = e;
        throw e;
      } finally {
        this.polling = false;
      }
    },
  },
});
