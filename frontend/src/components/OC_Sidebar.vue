<template>
  <aside class="tw-bg-gray-900 tw-w-full tw-h-full tw-flex tw-flex-col tw-border-r tw-border-gray-700 tw-pb-2">
    <!-- Header -->
    <div class="tw-p-4 tw-flex tw-items-center tw-space-x-3 tw-shrink-0 tw-border-b tw-border-gray-700">
      <img src="/app-icon.png" alt="App Icon" class="tw-w-8 tw-h-8 tw-rounded-md" />
      <h2 class="tw-font-bold tw-text-xl tw-text-white">Chokai Guide</h2>
      <button
        @click="$emit('close')"
        class="lg:tw-hidden tw-ml-auto tw-flex tw-items-center tw-justify-center tw-w-8 tw-h-8 tw-text-slate-300 hover:tw-bg-gray-700 tw-rounded-full tw-transition-colors"
        aria-label="サイドバーを閉じる"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="tw-h-5 tw-w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
    </div>

    <!-- App Usage Guide -->
    <div class="tw-flex-1 tw-overflow-y-auto tw-p-4">
      <div class="tw-space-y-4 tw-text-sm tw-text-gray-200">
        <h3 class="tw-font-semibold tw-text-base tw-text-white">{{ usageGuide.title }}</h3>
        <p>{{ usageGuide.description }}</p>
        <div>
          <p class="tw-mb-2">{{ usageGuide.prompt_intro }}</p>
          <ul class="tw-space-y-2">
            <li class="tw-p-3 tw-bg-gray-800/50 tw-rounded-lg tw-border tw-border-gray-700">
              <p class="tw-font-mono tw-text-gray-100">{{ usageGuide.prompt_1 }}</p>
            </li>
            <li class="tw-p-3 tw-bg-gray-800/50 tw-rounded-lg tw-border tw-border-gray-700">
              <p class="tw-font-mono tw-text-gray-100">{{ usageGuide.prompt_2 }}</p>
            </li>
          </ul>
        </div>
        <p>
          {{ usageGuide.map_info_1 }}<span class="tw-font-bold tw-text-blue-300">{{ usageGuide.map_info_highlight }}</span>{{ usageGuide.map_info_2 }}
        </p>
      </div>
    </div>

    <!-- User Info Area -->
    <div class="tw-shrink-0 tw-p-2">
      <div class="tw-p-2 tw-rounded-lg hover:tw-bg-gray-800 tw-transition-colors">
        <div class="tw-flex tw-items-center tw-space-x-3">
          <!-- User Icon -->
          <div class="tw-w-10 tw-h-10 tw-rounded-full tw-bg-slate-700 tw-flex tw-items-center tw-justify-center tw-text-white tw-font-semibold tw-text-lg">
            {{ userInitial }}
          </div>
          <!-- Username -->
          <span class="tw-flex-1 tw-font-semibold tw-text-white">{{ userStore.userName }}</span>
          <!-- Logout Button -->
          <button
            @click="handleLogout"
            class="tw-p-2 tw-text-slate-300 hover:tw-text-red-400 hover:tw-bg-red-500/20 tw-rounded-full tw-transition-colors"
            aria-label="ログアウト"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="tw-h-6 tw-w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue';
import { useUserStore } from '@/stores/user';
import { useChatStore } from '@/stores/chat';
import { useRouter } from 'vue-router';

const emit = defineEmits(['close']);
const userStore = useUserStore();
const chatStore = useChatStore();
const router = useRouter();

const usageGuide = computed(() => {
  const lang = userStore.user?.language || 'ja';
  switch (lang) {
    case 'en':
      return {
        title: "How to Use",
        description: "Plan your tour around Mt. Chokai by talking with our AI agent that recommends spots.",
        prompt_intro: "Try asking things like:",
        prompt_1: "Show recommended spots",
        prompt_2: "Add (spot name) to the plan",
        map_info_1: "The plan is reflected on the ",
        map_info_highlight: "Guidance Map",
        map_info_2: " on the right."
      };
    case 'zh':
      return {
        title: "使用方法",
        description: "与推荐鸟海山景点的人工智能代理交谈，制定您的景点游览计划。",
        prompt_intro: "请试着像这样提问：",
        prompt_1: "推荐一些景点",
        prompt_2: "将（景点名称）添加到计划中",
        map_info_1: "每次对话决定的计划将反映在",
        map_info_highlight: "导航地图",
        map_info_2: "上。"
      };
    default: // 'ja'
      return {
        title: "使い方",
        description: "鳥海山のスポットをオススメするAIエージェントと会話しながら、スポットの周遊計画を立てましょう。",
        prompt_intro: "次のように話しかけてみてください。",
        prompt_1: "おすすめのスポットを教えて",
        prompt_2: "〇〇をプランに追加して",
        map_info_1: "会話ごとに決まっていく計画は、画面右の",
        map_info_highlight: "ガイダンスマップ",
        map_info_2: "に反映されます。"
      };
  }
});

const userInitial = computed(() => {
  return userStore.userName ? userStore.userName.charAt(0).toUpperCase() : '?';
});

const handleLogout = () => {
  emit('close');
  userStore.logout();
  chatStore.clearChat();
  router.push('/login');
};
</script>