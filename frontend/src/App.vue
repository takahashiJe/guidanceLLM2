<script setup>
import { computed, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useNavStore } from '@/stores/nav'

const route = useRoute()
const navStore = useNavStore()

const deviceId = computed(() => navStore.deviceId)

// アプリケーションマウント時にUUIDを初期化
onMounted(() => {
  navStore.initializeDeviceId()
})

const isNavOrChat = computed(() => {
  return route.path === '/nav' || route.path === '/chat'
})
</script>

<template>
  <div id="app">
    <header v-if="!isNavOrChat">
      <img alt="Vue logo" class="logo" src="@/assets/logo.svg" width="125" height="125" />
      <div class="wrapper">
        <h1>Guidance LLM</h1>
      </div>
    </header>

    <RouterView />

    <footer class="device-id-footer" v-if="deviceId">
      Device ID: {{ deviceId }}
    </footer>
  </div>
</template>

<style scoped>
header {
  line-height: 1.5;
  max-height: 100vh;
}

.logo {
  display: block;
  margin: 0 auto 2rem;
}

.device-id-footer {
  position: fixed;
  bottom: 0;
  right: 0;
  padding: 2px 8px;
  background-color: rgba(0, 0, 0, 0.5);
  color: white;
  font-size: 10px;
  font-family: monospace;
  border-top-left-radius: 5px;
  z-index: 9999;
}

@media (min-width: 1024px) {
  header {
    display: flex;
    place-items: center;
    padding-right: calc(var(--section-gap) / 2);
  }

  .logo {
    margin: 0 2rem 0 0;
  }

  header .wrapper {
    display: flex;
    place-items: flex-start;
    flex-wrap: wrap;
  }
}
</style>