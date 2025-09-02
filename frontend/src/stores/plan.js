import { defineStore } from "pinia";
import { savePlanToIDB, getPlanFromIDB } from "@/lib/idb";
import { createPlan } from "@/lib/api";

export const usePlanStore = defineStore("plan", {
  state: () => ({
    plan: null, // PlanResponse
  }),
  actions: {
    async loadPlanFromApi(req) {
      const data = await createPlan(req);
      this.plan = data;
      await savePlanToIDB(data.pack_id, data);
      return data;
    },
    async loadPlanFromIdb(packId) {
      const data = await getPlanFromIDB(packId);
      if (data) this.plan = data;
      return !!data;
    },
    reset() {
      this.plan = null;
    },
  },
});

export async function ensurePlanLoaded(packId) {
  const store = usePlanStore();
  if (store.plan && store.plan.pack_id === packId) return true;
  return await store.loadPlanFromIdb(packId);
}
