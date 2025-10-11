<template>
  <div class="tw-py-4 tw-px-4 md:tw-px-8">
    <!-- User Message (unchanged) -->
    <div
      v-if="sender === 'user'"
      class="tw-flex tw-justify-end"
    >
      <div class="tw-max-w-xl">
        <div class="tw-px-4 tw-py-3 tw-rounded-2xl tw-bg-blue-100 tw-text-blue-900 tw-rounded-br-none tw-shadow-sm">
          <p class="tw-text-base tw-leading-relaxed tw-whitespace-pre-wrap">
            {{ content }}
          </p>
        </div>
      </div>
    </div>

    <!-- AI Message -->
    <div v-else class="tw-max-w-4xl tw-mx-auto">
      
      <!-- Pending/Spinner (unchanged) -->
      <div v-if="isPending" class="tw-flex tw-items-center tw-gap-4">
        <div class="tw-relative tw-w-8 tw-h-8">
          <svg class="tw-absolute tw-top-0 tw-left-0 tw-w-full tw-h-full animate-gemini-spinner-container" viewBox="0 0 24 24"><defs><linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#FF8A65" /><stop offset="50%" stop-color="#FFEB3B" /><stop offset="100%" stop-color="#69F0AE" /></linearGradient></defs><circle cx="12" cy="12" r="11" fill="none" stroke-width="2" class="tw-stroke-gray-200" opacity="0.3"></circle><circle cx="12" cy="12" r="11" fill="none" :stroke="`url(#${gradientId})`" stroke-width="2" class="animate-gemini-spinner-arc" stroke-linecap="round" stroke-dasharray="69.115"></circle></svg>
          <div class="tw-absolute tw-inset-0 tw-flex tw-items-center tw-justify-center"><img src="/app-icon.png" alt="App Icon" class="tw-w-5 tw-h-5 tw-rounded-full animate-icon-rotate" style="transform-origin: 50% 50%;"></div>
        </div>
        <p class="tw-text-base tw-text-gray-600">お待ちください...</p>
      </div>

      <!-- Rendered Markdown Content -->
      <div v-if="!isPending">
        <div class="tw-w-8 tw-h-8 tw-flex tw-items-center tw-justify-start tw-shrink-0">
          <img src="/app-icon.png" alt="App Icon" class="tw-w-6 tw-h-6 tw-rounded-full">
        </div>
        <div
          class="tw-prose tw-prose-zinc lg:tw-prose-lg tw-max-w-none tw-text-gray-800 tw-pt-2"
          v-html="formattedContent"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { marked } from 'marked';

const gradientId = `spinner-gradient-${Math.random().toString(36).substring(2, 9)}`;

const props = defineProps({
  sender: { type: String, required: true },
  content: { type: String, required: true },
  isPending: { type: Boolean, default: false },
});

// Computed property to convert markdown content to HTML
const formattedContent = computed(() => {
  if (props.content) {
    return marked.parse(props.content);
  }
  return '';
});

</script>

<!-- The <style scoped> block has been removed as the animation is no longer used -->
