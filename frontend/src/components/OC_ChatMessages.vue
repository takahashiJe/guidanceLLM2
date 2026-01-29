<template>
  <div class="tw-p-4 tw-space-y-6">
    <OC_ChatMessage
      v-for="message in messages"
      :key="message.id"
      :sender="message.sender"
      :content="message.text || message.content" 
      :is-pending="message.isPending"
    />
  </div>
</template>

<script setup>
import OC_ChatMessage from './OC_ChatMessage.vue';

defineProps({
  messages: {
    type: Array,
    required: true,
  },
});
</script>