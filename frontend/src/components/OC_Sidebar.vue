<template>
  <aside class="tw-bg-white tw-w-full tw-h-full tw-p-4 tw-flex tw-flex-col tw-border-r tw-border-gray-200">
    <div class="tw-flex tw-items-center tw-space-x-3 shrink-0 tw-mb-6">
      <button
        @click="$emit('close')"
        class="lg:tw-hidden tw-flex tw-items-center tw-justify-center tw-w-8 tw-h-8 tw-bg-white tw-rounded-full tw-shadow tw-text-gray-600 hover:tw-bg-gray-100 tw-transition-colors"
        aria-label="サイドバーを閉じる"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="tw-h-5 tw-w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
      <h2 class="tw-font-bold tw-text-lg tw-text-gray-800">メニュー</h2>
    </div>

    <div class="tw-flex-1 tw-flex tw-flex-col tw-space-y-4 tw-overflow-y-auto">
      <!-- Content of the sidebar can be added here in the future -->
    </div>

    <div class="tw-shrink-0 tw-pt-4">
      <button
        @click="handleLogout"
        class="tw-flex tw-items-center tw-space-x-3 tw-w-full tw-text-left tw-text-gray-600 hover:tw-bg-gray-100 tw-py-2 tw-px-4 tw-rounded-lg tw-transition-colors tw-duration-200"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="tw-h-6 tw-w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
        <span class="tw-font-semibold">ログアウト</span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { useUserStore } from '@/stores/user';
import { useChatStore } from '@/stores/chat';
import { useRouter } from 'vue-router';

const emit = defineEmits(['close']);
const userStore = useUserStore();
const chatStore = useChatStore();
const router = useRouter();

const handleLogout = () => {
  emit('close');
  userStore.logout();
  chatStore.clearChat();
  router.push('/login');
};
</script>
