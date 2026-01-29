<template>
  <div class="tw-py-4 tw-px-4 md:tw-px-8">
    <!-- User Message -->
    <div
      v-if="sender === 'user'"
      class="tw-flex tw-justify-end"
    >
      <div class="tw-max-w-xl">
        <div class="tw-px-4 tw-py-3 tw-rounded-2xl tw-bg-blue-800 tw-text-white tw-rounded-br-none tw-shadow-sm">
          <p class="tw-text-base tw-leading-relaxed tw-whitespace-pre-wrap">
            {{ content }}
          </p>
        </div>
      </div>
    </div>

    <!-- AI Message -->
    <div v-else class="tw-max-w-4xl tw-mx-auto">
      <!-- Pending/Spinner -->
      <div v-if="isPending" class="tw-flex tw-items-center tw-gap-4">
        <div class="tw-relative tw-w-8 tw-h-8">
          <svg class="tw-absolute tw-top-0 tw-left-0 tw-w-full tw-h-full tw-overflow-visible animate-gemini-spinner-container" viewBox="0 0 24 24">
            <defs>
              <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#FF8A65" />
                <stop offset="50%" stop-color="#FFEB3B" />
                <stop offset="100%" stop-color="#69F0AE" />
              </linearGradient>
            </defs>
            <circle cx="12" cy="12" r="11" fill="none" stroke-width="2.5" class="tw-stroke-gray-500" opacity="0"></circle>
            <circle cx="12" cy="12" r="11" fill="none" :stroke="`url(#${gradientId})`" stroke-width="2.5" class="animate-gemini-spinner-arc" stroke-linecap="round" stroke-dasharray="69.115"></circle>
          </svg>
          <div class="tw-absolute tw-inset-0 tw-flex tw-items-center tw-justify-center">
            <img 
              src="/app-icon.png" 
              alt="App Icon" 
              class="tw-w-5 tw-h-5 tw-rounded-full animate-icon-rotate" 
              style="transform-origin: 50% 50%; box-shadow: 0 0 10px rgba(255, 255, 255, 0.4);"
            >
          </div>
        </div>
        <p class="tw-text-base tw-text-gray-200">{{ pendingText }}</p>
      </div>

      <!-- Rendered Markdown Content -->
      <div v-if="!isPending">
        <div class="tw-w-8 tw-h-8 tw-flex tw-items-center tw-justify-start tw-shrink-0">
          <img src="/app-icon.png" alt="App Icon" class="tw-w-6 tw-h-6 tw-rounded-full">
        </div>
        <div
          class="tw-prose tw-prose-invert tw-prose-zinc lg:tw-prose-lg tw-max-w-none tw-pt-2 prose-p:tw-text-gray-50 prose-li:tw-text-gray-50 prose-headings:tw-text-white"
          v-html="formattedContent"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onUnmounted } from 'vue';
import { marked } from 'marked';
import { useUserStore } from '@/stores/user';

const props = defineProps({
  sender: { type: String, required: true },
  content: { type: String, required: true },
  isPending: { type: Boolean, default: false },
});

const userStore = useUserStore();
const gradientId = `spinner-gradient-${Math.random().toString(36).substring(2, 9)}`;

const displayedContent = ref('');
let wordInterval = null;

watch(() => props.isPending, (isPending, wasPending) => {
  // Animate when loading is finished
  if (wasPending && !isPending && props.content) {
    displayedContent.value = '';
    clearInterval(wordInterval);

    // Split by spaces and newlines, but keep them in the array to preserve formatting
    const words = props.content.split(/(\s+)/);
    let wordIndex = 0;

    wordInterval = setInterval(() => {
      if (wordIndex < words.length) {
        displayedContent.value += words[wordIndex];
        wordIndex++;
      } else {
        clearInterval(wordInterval);
      }
    }, 40); // ms per word/space
  }
});

// If the component is mounted with content already (e.g. from chat history), display it directly
if (!props.isPending && props.content) {
  displayedContent.value = props.content;
}

onUnmounted(() => {
  clearInterval(wordInterval);
});

const formattedContent = computed(() => {
  return marked.parse(displayedContent.value || '');
});

const pendingText = computed(() => {
  const lang = userStore.user?.language || 'ja';
  switch (lang) {
    case 'en':
      return 'Please wait...';
    case 'zh':
      return '请稍候...';
    default: // 'ja'
      return 'お待ちください...';
  }
});
</script>
