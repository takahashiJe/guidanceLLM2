// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import NavView from '../views/NavView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'nav', component: NavView },
  ],
})

export default router
