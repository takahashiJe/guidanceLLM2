import { createRouter, createWebHistory } from "vue-router";
import { usePlanStore } from "@/stores/plan";
import { ensurePlanLoaded } from "@/stores/plan"; // 再利用のためエクスポート

const routes = [
  { path: "/", component: () => import("@/pages/PlanSetup.vue") },
  {
    path: "/prefetch/:packId",
    component: () => import("@/pages/Prefetch.vue"),
    beforeEnter: () => {
      const plan = usePlanStore();
      return plan.plan ? true : "/";
    },
  },
  {
    path: "/nav/:packId",
    component: () => import("@/pages/Navigator.vue"),
    beforeEnter: async (to) => {
      const ok = await ensurePlanLoaded(to.params.packId);
      return ok ? true : "/";
    },
  },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
