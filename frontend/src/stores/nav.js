// src/stores/nav.js
import { defineStore } from 'pinia';
import { openDB } from 'idb';
import { createPlan, pollPlan } from '@/lib/api';

const DB_NAME = 'navpacks';
const DB_VERSION = 1;

async function getDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('packs')) {
        db.createObjectStore('packs', { keyPath: 'pack_id' });
      }
    }
  });
}

async function prefetchAssets(plan) {
  if (!plan?.assets) return;
  const cache = await caches.open('nav-audio-v1');
  const db = await getDB();

  const tasks = plan.assets
    .map(a => a?.audio?.url)
    .filter(Boolean)
    .map(async (url) => {
      try {
        await cache.add(new Request(url, { credentials: 'same-origin' }));
      } catch {
        // 既にキャッシュ済み or ネットワーク一時失敗は無視
      }
    });

  await Promise.all(tasks);
  await db.put('packs', { pack_id: plan.pack_id, saved_at: Date.now(), assets: plan.assets });
}

export const useNavStore = defineStore('nav', {
  state: () => ({
    lang: 'ja',
    waypoints: [],        // ['spot_001', ...]
    origin: JSON.parse(localStorage.getItem('nav.origin') || 'null'), // ← 復元
    taskId: null,
    polling: false,
    plan: null,           // 最終 Plan レスポンス
  }),

  actions: {
    setLang(l) { this.lang = l; },
    setWaypoints(arr) { this.waypoints = Array.from(new Set(arr)); },
    setOrigin(o) {
      this.origin = { lat: o.lat, lon: o.lon };
      localStorage.setItem('nav.origin', JSON.stringify(this.origin));
    },
    clearPlan() { this.plan = null; this.taskId = null; },

    // ✅ 追加：Plan をストアに保存してプリフェッチも走らせる
    setPlan(plan) {
      this.plan = plan;
      prefetchAssets(plan).catch(() => {});
    },

    // （任意）ストアだけで作成〜ポーリングまでやりたい場合に使えるヘルパ
    async submitPlan() {
      if (!this.origin) throw new Error('現在地が未取得です');
      if (this.waypoints.length < 2) throw new Error('スポットは2か所以上選んでください');

      const payload = {
        language: this.lang,
        origin: { lat: this.origin.lat, lon: this.origin.lon },
        return_to_origin: true,
        waypoints: this.waypoints.map(id => ({ spot_id: id })),
      };

      const { task_id } = await createPlan(payload);
      this.taskId = task_id;
      this.polling = true;

      const plan = await pollPlan(task_id);
      this.polling = false;

      this.setPlan(plan); // 上の setPlan を使用
      return plan;        // 呼び出し側で router.push('/nav') など可能
    },
  },
});
