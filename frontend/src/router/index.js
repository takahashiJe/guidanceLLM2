// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import PlanView from '@/views/PlanView.vue'
import NavView from '@/views/NavView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/plan' },
    { path: '/plan', name: 'plan', component: PlanView },
    { path: '/nav',  name: 'nav',  component: NavView },
    // 404 fallback（任意）
    { path: '/:pathMatch(.*)*', redirect: '/plan' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

export default router
