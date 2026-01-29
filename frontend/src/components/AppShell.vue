<template>
  <div class="tw-h-screen tw-w-screen tw-bg-gray-800">
    <!-- Static Sidebar for large screens -->
    <div class="tw-hidden lg:tw-block tw-fixed tw-top-0 tw-left-0 tw-h-full tw-w-[260px] tw-z-20">
      <OC_Sidebar />
    </div>

    <div class="tw-h-full tw-flex tw-flex-col lg:tw-pl-[260px]">
      <!-- Unified Header -->
      <header class="tw-p-3 tw-border-b tw-border-gray-700 tw-flex tw-items-center tw-gap-4 tw-shrink-0 tw-bg-gray-800 tw-z-10 tw-touch-action-none">
        <!-- Hamburger for mobile -->
        <button @click="isSidebarOpen = true" class="tw-p-1 tw-rounded-full hover:tw-bg-gray-700 lg:tw-hidden">
          <svg xmlns="http://www.w3.org/2000/svg" class="tw-h-6 tw-w-6 tw-text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
        <!-- Title -->
        <h1 class="tw-text-base tw-font-semibold tw-text-white">AI Agent by Qwen3</h1>
      </header>

      <!-- Main Content -->
      <main class="tw-flex-1 tw-overflow-hidden tw-overscroll-y-contain">
        <RouterView />
      </main>
    </div>

    <!-- Mobile Sidebar (sliding) -->
    <transition name="fade">
      <div v-if="isSidebarOpen" @click="isSidebarOpen = false" class="tw-fixed tw-inset-0 tw-bg-black tw-bg-opacity-50 tw-z-40 lg:tw-hidden"></div>
    </transition>
    <transition name="slide-left">
      <div v-if="isSidebarOpen" class="tw-fixed tw-top-0 tw-left-0 tw-w-3/4 tw-max-w-sm tw-h-full tw-bg-white tw-shadow-xl tw-z-50 lg:tw-hidden">
        <OC_Sidebar @close="isSidebarOpen = false" />
      </div>
    </transition>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { RouterView } from 'vue-router';
import OC_Sidebar from './OC_Sidebar.vue';
import { useChatStore } from '@/stores/chat';
import { useUserStore } from '@/stores/user';

const isSidebarOpen = ref(false);

// Rehydrate session on component mount
onMounted(async () => {
  const chatStore = useChatStore();
  const userStore = useUserStore();
  console.log(`[AppShell] Component mounted. Checking auth status...`);
  console.log(`[AppShell] isLoggedIn: ${userStore.isLoggedIn}`);
  console.log(`[AppShell] userName: ${userStore.userName}`);
  console.log('[AppShell] Attempting to rehydrate session...');
  await chatStore.rehydrateSession();
  console.log('[AppShell] Session rehydration process finished.');
});
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.slide-left-enter-active, .slide-left-leave-active { transition: transform 0.3s ease-in-out; }
.slide-left-enter-from, .slide-left-leave-to { transform: translateX(-100%); }
</style>