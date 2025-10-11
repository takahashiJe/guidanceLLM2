<script setup>
import { ref, watch, nextTick, onMounted, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'

// Preserved from original component
import NavWindow from '@/components/NavWindow.vue'

// New UI components
import OC_ChatMessages from '@/components/OC_ChatMessages.vue';
import OC_ChatInput from '@/components/OC_ChatInput.vue';

const userStore = useUserStore()
const chatStore = useChatStore()
const { messages, isLoading, isSessionLoaded } = storeToRefs(chatStore)

const messagesContainer = ref(null);

// --- New state for suggestion prompts ---
const chatInputText = ref('');
const suggestionTemplates = computed(() => {
  const lang = userStore.user?.language || 'ja';
  switch (lang) {
    case 'en':
      return [
        'Show recommended spots',
        'Add (Spot Name) to the plan',
        'Where can I eat?'
      ];
    case 'zh':
      return [
        '推荐一些景点',
        '将（景点名称）添加到计划中',
        '告诉我可以在哪里吃饭'
      ];
    default: // 'ja'
      return [
        'おすすめのスポットを教えて',
        '（スポット名）をプランに追加して',
        '食事ができるところを教えて'
      ];
  }
});

function applySuggestion(template) {
  chatInputText.value = template;
}
// -------------------------------------

async function handleSendMessage() {
  if (!chatInputText.value.trim()) return;
  await chatStore.sendMessage(chatInputText.value);
  // The input will be cleared by the child component via v-model update
}

// Function to scroll to the bottom of the messages container
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
};

// Watch for changes in the number of messages and scroll to bottom
watch(() => messages.value.length, () => {
  scrollToBottom();
});

watch(isSessionLoaded, (isLoaded) => {
  if (isLoaded && messages.value.length === 0) {
    console.log('[ChatView] Session loaded and chat is empty. Adding welcome message.');
    const lang = userStore.user?.language || 'ja';
    let welcomeMessage = '';

    switch (lang) {
      case 'en':
        welcomeMessage = `Hello, ${userStore.userName}. This app helps you create sightseeing plans for Mt. Chokai and find information about nearby spots through a conversation with an AI. To get started, try asking, "Show me some recommended spots"!`;
        break;
      case 'zh':
        welcomeMessage = `你好, ${userStore.userName}。通过与AI对话，您可以使用此应用程序创建鸟海山的观光计划，并查找附近景点的信息。首先，让我们试着问“请告诉我推荐的景点”！`;
        break;
      default: // 'ja'
        welcomeMessage = `こんにちは、${userStore.userName}さん。このアプリは、AIとの対話を通じて鳥海山の観光プランを作成したり、周辺のスポット情報を調べたりすることができます。まずは「おすすめのスポットを教えて」と聞いてみましょう！`;
        break;
    }

    messages.value.push({
      id: 'initial-welcome',
      content: welcomeMessage,
      sender: 'ai',
      timestamp: new Date(),
    });
  }
});

// When the component is first mounted
onMounted(() => {
  scrollToBottom(); // Also scroll to bottom on initial load
});

</script>

<template>
  <!-- The NavWindow component is preserved here, outside the new chat UI div -->
  <NavWindow />

  <div class="tw-relative tw-w-full tw-h-full tw-flex tw-flex-col bg-noise">
    <!-- Message List Area -->
    <div class="tw-flex-1 tw-overflow-y-auto tw-pb-28" ref="messagesContainer">
      <OC_ChatMessages :messages="messages" />
    </div>

    <!-- Floating Suggestion Cards -->
    <div class="tw-absolute tw-bottom-[88px] tw-left-0 tw-w-full tw-z-10">
        <div class="no-scrollbar tw-flex tw-gap-2 tw-overflow-x-auto tw-px-4">
          <button 
            v-for="template in suggestionTemplates" 
            :key="template"
            @click="applySuggestion(template)"
            class="tw-flex-shrink-0 tw-p-2 tw-px-3 tw-border tw-border-gray-400/50 tw-rounded-lg tw-text-sm tw-text-gray-800 tw-bg-white/70 tw-backdrop-blur-sm hover:tw-bg-gray-200/70 tw-transition-colors"
          >
            {{ template }}
          </button>
        </div>
      </div>

    <!-- Input Area -->
    <div class="tw-shrink-0 tw-bg-white tw-border-t tw-border-gray-200">
      <OC_ChatInput v-model="chatInputText" @sendMessage="handleSendMessage" :is-sending="isLoading" />
    </div>
  </div>
</template>

<style>
/* Utility to hide the scrollbar */
.no-scrollbar::-webkit-scrollbar {
    display: none;
}
.no-scrollbar {
    -ms-overflow-style: none;  /* IE and Edge */
    scrollbar-width: none;  /* Firefox */
}
</style>