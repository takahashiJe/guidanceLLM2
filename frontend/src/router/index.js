// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router';

const PlanView = () => import('@/views/PlanView.vue');
const NavView  = () => import('@/views/NavView.vue');

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/plan' },
    { path: '/plan', name: 'plan', component: PlanView },
    { path: '/nav',  name: 'nav',  component: NavView  },
  ],
});

export default router;
