<template>
  <div 
    class="tw-bg-slate-50/90 tw-backdrop-blur-lg"
    style="box-shadow: 0 -8px 32px -10px rgba(0, 0, 0, 0.08);"
  >
    <div class="tw-max-w-4xl tw-mx-auto tw-px-4 tw-py-3">
      <div class="tw-relative tw-flex tw-items-end tw-gap-2">
        <textarea
          ref="textarea"
          v-model="value"
          @input="adjustTextareaHeight"
          @keydown.enter.prevent="handleEnter"
          :placeholder="placeholder"
          class="tw-flex-1 tw-bg-slate-100 focus:tw-bg-slate-200/60 tw-rounded-2xl tw-border-none focus:tw-ring-0 tw-resize-none tw-py-2.5 tw-px-4 tw-text-base tw-text-gray-800 placeholder:tw-text-gray-500 tw-transition-colors tw-duration-200"
          rows="1"
          style="max-height: 200px;"
        ></textarea>
        <button
          @click="handleSendMessage"
          :disabled="props.isSending || value.trim() === ''"
          class="tw-w-9 tw-h-9 tw-rounded-full tw-flex-shrink-0 tw-flex tw-items-center tw-justify-center tw-transition-all tw-duration-200 tw-mb-0.5"
          :class="props.isSending || value.trim() === '' 
            ? 'tw-text-slate-400 tw-cursor-not-allowed' 
            : 'tw-bg-slate-800 tw-text-white hover:tw-bg-slate-700 active:tw-scale-90'"
          aria-label="メッセージを送信"
        >
          <svg v-if="props.isSending" class="tw-animate-spin tw-h-5 tw-w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="tw-opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="tw-opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="tw-h-5 tw-w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <polyline points="19 12 12 19 5 12"></polyline>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue';

const props = defineProps({
  isSending: {
    type: Boolean,
    default: false,
  },
  modelValue: { // for v-model
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: 'Send a message...'
  }
});

const emit = defineEmits(['sendMessage', 'update:modelValue']); // for v-model

const textarea = ref(null);

// Computed property to proxy v-model
const value = computed({
  get() {
    return props.modelValue;
  },
  set(newValue) {
    emit('update:modelValue', newValue);
  }
});

const adjustTextareaHeight = () => {
  const el = textarea.value;
  if (el) {
    el.style.height = 'auto'; // Reset height to shrink if text is deleted
    el.style.height = `${el.scrollHeight}px`;
  }
};

const handleEnter = (event) => {
  if (event.shiftKey) return; 
  handleSendMessage();
};

const handleSendMessage = () => {
  if (props.isSending || value.value.trim() === '') return;
  
  emit('sendMessage', value.value.trim());
  // Clear the input via the v-model update
  emit('update:modelValue', '');
  
  nextTick(() => {
    adjustTextareaHeight();
  });
};

// Watch for external changes and initial load
watch(() => props.modelValue, () => {
  nextTick(adjustTextareaHeight);
}, { immediate: true });

</script>