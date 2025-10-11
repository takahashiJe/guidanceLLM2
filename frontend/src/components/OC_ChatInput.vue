<template>
  <div class="tw-p-4 tw-bg-white">
    <div class="tw-max-w-4xl tw-mx-auto">
      <div class="tw-flex tw-items-center tw-bg-[#f0f4f9] tw-rounded-full tw-p-2">
        <textarea
          ref="textarea"
          v-model="value"
          @input="adjustTextareaHeight"
          @keydown.enter.prevent="handleEnter"
          placeholder="メッセージを入力..."
          class="tw-flex-1 tw-bg-transparent tw-border-none focus:tw-ring-0 tw-resize-none tw-p-2 tw-text-base tw-text-gray-800 placeholder:tw-text-gray-500"
          rows="1"
        ></textarea>
        <button
          @click="handleSendMessage"
          :disabled="props.isSending || value.trim() === ''"
          class="tw-w-10 tw-h-10 tw-rounded-full tw-flex tw-items-center tw-justify-center tw-transition-colors"
          :class="props.isSending || value.trim() === '' ? 'tw-bg-gray-300' : 'tw-bg-blue-500 hover:tw-bg-blue-600'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="tw-h-5 tw-w-5 tw-text-white" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.428A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
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
    el.style.height = 'auto';
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

watch(value, adjustTextareaHeight);

// Adjust height when the prop is changed externally
watch(() => props.modelValue, () => {
  nextTick(adjustTextareaHeight);
});

</script>