import { defineStore } from "pinia";
import { prefetchViaSW } from "@/lib/sw";

export const useAssetsStore = defineStore("assets", {
  state: () => ({
    prefetch: { total: 0, done: 0, state: "idle", error: null },
  }),
  actions: {
    async prefetchAll(assets) {
      this.prefetch = { total: assets.length, done: 0, state: "running", error: null };
      try {
        const urls = assets.map((a) => a.audio.url);
        const res = await prefetchViaSW(urls);
        if (!res?.ok) throw new Error("prefetch failed");
        this.prefetch = { total: urls.length, done: urls.length, state: "done", error: null };
        return true;
      } catch (e) {
        this.prefetch = { ...this.prefetch, state: "error", error: e?.message || String(e) };
        return false;
      }
    },
    reset() {
      this.prefetch = { total: 0, done: 0, state: "idle", error: null };
    },
  },
});
