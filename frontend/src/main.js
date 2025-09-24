// src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import { buildSpotCodeMap } from '@/lib/spotCodes'
import router from './router'
import App from './App.vue'
import './assets/base.css'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

app.use(pinia)
app.use(createPinia())
app.use(router)
app.mount('#app')
buildSpotCodeMap()

// Service Worker（public/sw.js がある前提）
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}
